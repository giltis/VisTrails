'''
Created on Dec 15, 2010

@author: tpmaxwel
'''
import sys, threading, traceback
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from gui.modules.module_configure import StandardModuleConfigurationWidget
from core.vistrail.port import PortEndPoint
from core.modules.vistrails_module import Module, ModuleError
from core.interpreter.default import get_default_interpreter as getDefaultInterpreter
from core.modules.basic_modules import Integer, Float, String, Boolean, Variant
from packages.vtDV3D.ColorMapManager import ColorMapManager 
from core.utils import getHomeRelativePath, getFullPath
from packages.vtDV3D.CDATTask import deserializeTaskData
from packages.vtDV3D import HyperwallManager
from collections import OrderedDict
from packages.vtDV3D.vtUtilities import *
import cdms2, cdtime


class CDMSDataType:
    Volume = 1
    Slice = 2
    Vector = 3
    Hoffmuller = 4
    ChartData = 5
    
class ConfigPopupManager( QObject ):
    
    def __init__( self, **args ):
        self.menu = QMenu()
        self.resetActions = True
        self.connect ( self.menu, SIGNAL("aboutToHide()"), lambda: self.reset() )
            
    def show( self, module, x, y ):
        if self.resetActions: 
            self.resetActions = False
            self.menu.clear()  
            self.actionMap = {}
            
        for configFunc in module.configurableFunctions.values():
            action_key = str( configFunc.label )
            menuItem = self.menu.addAction( action_key )
            self.actionMap.setdefault( action_key, [] ).append( ( module, configFunc.key ) ) 
            self.connect ( menuItem, SIGNAL("triggered()"), lambda akey=action_key: self.execAction( akey ) )

        if self.menu.isHidden():    
            self.menu.popup( QCursor.pos() )
        else:                       
            self.menu.updateGeometry()
    
    def execAction( self, action_key ): 
        print " execAction: ", action_key
        actionList  =  self.actionMap[ action_key ]
        for ( module, key ) in actionList:
            module.processKeyEvent( key )
                
    def reset(self):
        self.resetActions = True

class WindowRefinementGenerator( QObject ):

    def __init__( self, **args ):
        self.initialPosition = None
        self.initialRefinement = None
        self.range = args.get( 'range', [ 0.0, 1.0 ] )
        
    def initRefinement( self, pos, initRefinement ):  
        self.initialPosition = pos
        self.initialRefinement = initRefinement
        
    def updateRefinement( self, pos, wsize ):
        newRefinement = [ 0, 0 ]
        scale = self.range[1] - self.range[0]
        for iR in [ 0, 1 ]:
            dr = ( pos[iR] - self.initialPosition[iR] ) * scale / wsize[iR]
            newRefinement[iR] = self.initialRefinement[iR] + dr
            if newRefinement[iR] < self.range[0]: newRefinement[iR] = self.range[0]
            if newRefinement[iR] > self.range[1]: newRefinement[iR] = self.range[1]
        return newRefinement

class QtWindowLeveler( QObject ):
    
    update_range_signal = SIGNAL('update_range')
    
    WindowRelative = 0
    BoundsRelative = 1
    Absolute = 2
   
    def __init__( self, **args ):
        QObject.__init__( self )
        self.OriginalWindow           = 1.0
        self.OriginalLevel            = 0.5
        self.CurrentWindow            = 1.0
        self.CurrentLevel             = 0.5
        self.sensitivity              = args.get( 'sensitivity', (1.5, 5.0) )
        self.algorithm                = self.WindowRelative if args.get( 'windowing', True ) else self.Absolute
        self.scaling = 1.0        
        self.invert = False

    def setDataRange( self, data_range ):
        if (self.algorithm == self.Absolute):
            self.setWindowLevel( data_range[0], data_range[1] )
        else:
            self.scaling = 0.5 * ( abs(data_range[0]) + abs(data_range[1]) )
            self.OriginalWindow = ( data_range[1] - data_range[0] ) / self.scaling if ( self.scaling > 0.0 ) else 1.0
            self.OriginalLevel = 1.0
          
            if( abs( self.OriginalWindow ) < 0.001 ): self.OriginalWindow = -0.001 if ( self.OriginalWindow < 0.0 ) else  0.001
            if( abs( self.OriginalLevel  ) < 0.001 ): self.OriginalLevel  = -0.001 if ( self.OriginalLevel  < 0.0 ) else  0.001
            self.setWindowLevel( self.OriginalWindow, self.OriginalLevel )
    
    def addUpdateRangeObserver( self, observer ):   
        self.connect( self, self.update_range_signal, observer )

    def windowLevel( self, X, Y, window_size ):
        result = None
        if self.algorithm == self.WindowRelative:
              window = self.InitialWindow
              level = self.InitialLevel
                
              dx = self.sensitivity[0] * ( X - self.StartWindowLevelPositionX ) / float( window_size[0] )
              dy = self.sensitivity[1] * ( self.StartWindowLevelPositionY - Y ) / float( window_size[1] )
               
              if ( abs( window ) > 0.01 ):   dx = dx * window
              else:                          dx = (dx * -0.01) if ( window < 0 ) else (dx *  0.01)
        
              if ( abs( level  ) > 0.01 ):   dy = dy * level
              else:                          dy = (dy * -0.01) if ( window < 0 ) else (dy *  0.01)
                
              if ( window < 0.0 ):           dx = -1 * dx
              if ( level < 0.0 ):            dy = -1 * dy
             
              newWindow = dx + window
              newLevel = level - dy
            
              if ( abs( newWindow ) < 0.01 ):  newWindow = -0.01 if( newWindow < 0 ) else  0.01 
              if ( abs( newLevel ) < 0.01 ):   newLevel  = -0.01 if( newLevel  < 0 ) else  0.01 
              
              if (( (newWindow < 0) and (self.CurrentWindow > 0 )) or ( (newWindow > 0) and (self.CurrentWindow < 0) )):
                  self.invert = not self.invert
            
              rmin = newLevel - 0.5*abs( newWindow )
              rmax = rmin + abs( newWindow )
              result = [ rmin*self.scaling, rmax*self.scaling, 1 if self.invert else 0 ]
              self.emit( self.update_range_signal, result )
            
              self.CurrentWindow = newWindow
              self.CurrentLevel = newLevel
        elif self.algorithm == self.BoundsRelative:
              dx =  self.sensitivity[0] * ( X - self.StartWindowLevelPositionX ) 
              dy =  self.sensitivity[1] * ( Y - self.StartWindowLevelPositionY ) 
              rmin = self.InitialRange[0] + ( dx / window_size[0] ) * self.InitialWindow
              rmax = self.InitialRange[1] + ( dy / window_size[1] ) * self.InitialWindow
              if rmin > rmax:   result =  [ rmax, rmin, 1 ]
              else:             result =  [ rmin, rmax, 0 ]
              self.CurrentWindow = result[1] - result[0]
              self.CurrentLevel =  0.5 * ( result[0] + result[1] )
        elif self.algorithm == self.Absolute:
              dx =  1.0 + self.sensitivity[0] * ( ( X - self.StartWindowLevelPositionX )  / self.StartWindowLevelPositionX ) 
              dy =  1.0 + self.sensitivity[1] * ( ( Y - self.StartWindowLevelPositionY ) / self.StartWindowLevelPositionY ) 
              self.CurrentWindow = dx*self.InitialWindow
              self.CurrentLevel =  dy*self.InitialLevel
              print str( [dx,dy,self.CurrentWindow,self.CurrentLevel] )
              result = [ self.CurrentWindow, self.CurrentLevel, 0 ]
              self.emit( self.update_range_signal, result )
 #       print " --- Set Range: ( %f, %f ),   Initial Range = ( %f, %f ), P = ( %d, %d ) dP = ( %f, %f ) " % ( result[0], result[1], self.InitialRange[0], self.InitialRange[1], X, Y, dx, dy )      
        return result
      
    def startWindowLevel( self, X, Y ):   
        self.InitialWindow = self.CurrentWindow
        self.InitialLevel = self.CurrentLevel  
        self.StartWindowLevelPositionX = float(X)
        self.StartWindowLevelPositionY = float(Y)
        rmin = self.InitialLevel - 0.5 * abs( self.CurrentWindow )
        rmax = rmin + abs( self.CurrentWindow )
        self.InitialRange = [ rmin, rmax ] if ( rmax > rmin ) else [ rmax, rmin ]
#        print " --- Initialize Range: ( %f, %f ), P = ( %d, %d ) WL = ( %f, %f ) " % ( self.InitialRange[0]*self.scaling, self.InitialRange[1]*self.scaling, X, Y, self.InitialWindow, self.InitialLevel )     

    def setWindowLevel( self, window,  level ):
        if ( (self.CurrentWindow == window) and (self.CurrentLevel == level) ): return
        
        if (( (window < 0) and (self.CurrentWindow > 0 )) or ( (window > 0) and (self.CurrentWindow < 0) )):
              self.invert = not self.invert
        
        if window < 0.01:
            pass      
        self.CurrentWindow = window
        self.CurrentLevel = level
        
        rmin = self.CurrentLevel - 0.5 * abs( self.CurrentWindow )
        rmax = rmin + abs( self.CurrentWindow )
        result = [ rmin*self.scaling, rmax*self.scaling, 1 if self.invert else 0 ]
        self.emit( self.update_range_signal, result )

        return result

    def setWindowLevelFromRange( self, range ):
        self.CurrentWindow = ( range[1] - range[0] ) / self.scaling
        self.CurrentLevel = ( range[1] + range[0] ) / ( 2 * self.scaling )
        

###############################################################################   

class OutputRecManager: 
    
    sep = ';#:|!'   
            
    def __init__( self, serializedData = None ): 
        self.outputRecs = {}
        if serializedData <> None:
            self.deserialize( serializedData )
            
    def deleteOutput( self, dsid, outputName ):
        orecMap =  self.outputRecs.get( dsid, None )
        if orecMap: del orecMap[outputName] 

    def addOutputRec( self, dsid, orec ): 
        orecMap =  self.outputRecs.setdefault( dsid, {} )
        orecMap[ orec.name ] = orec

    def getOutputRec( self, dsid, outputName ):
        orecMap =  self.outputRecs.get( dsid, None )
        return orecMap[ outputName ] if orecMap else None

    def getOutputRecNames( self, dsid  ): 
        orecMap =  self.outputRecs.get( dsid, None )
        return orecMap.keys() if orecMap else []

    def getOutputRecs( self, dsid ):
        orecMap =  self.outputRecs.get( dsid, None )
        return orecMap.values() if orecMap else []
        
    def deserialize( self, serializedData ): 
        self.outputRecs = {}  
        outputRecData = serializedData.split( OutputRecManager.sep[0] )
        for outputRecItem in outputRecData:
            if outputRecItem:
                outputFields = outputRecItem.split( OutputRecManager.sep[1] )
                if outputFields:
                    try: 
                        varList = []
                        dsid = outputFields[0]
                        port_data = outputFields[1]
                        port_data_fields = port_data.split( OutputRecManager.sep[2] )
                        name = port_data_fields[0]
                        ndim = int( port_data_fields[1] )
                        variables = outputFields[2].split( OutputRecManager.sep[2] ) 
                        selectedLevel = outputFields[3] if ( len( outputFields ) > 3 ) else None
                        if variables: 
                            for varEntry in variables:
                                varRec = varEntry.split( OutputRecManager.sep[3] ) 
                                if len( varRec[0] ) > 0: varList.append( varRec )                            
                        orec = OutputRec( name, ndim=ndim, varList=varList, level=selectedLevel ) 
                        self.addOutputRec( dsid, orec ) 
                    except Exception, err:
                        print "Error deserializing port data: %s " % ( str( err ) )
                        
                            
    def serialize( self ):        
        portData = []
        for oRecData in self.outputRecs.items():
            dsetId = oRecData[0]
            orecMap = oRecData[1]
            for oRec in orecMap.values():
                port_name = oRec.name
                port_table = oRec.varTable
                nVarDims = oRec.ndim
                portData.append( "%c%s%c" % ( OutputRecManager.sep[0], dsetId, OutputRecManager.sep[1] ) )
                if port_table <> None:
                    portData.append( "%s%c%d%c" % (  port_name, OutputRecManager.sep[2], nVarDims, OutputRecManager.sep[1] ) )
                    for iRow in range( port_table.rowCount() ):
                        varNameLabel = port_table.cellWidget( iRow, 0 )
                        varName = str( varNameLabel.text() )
                        portData.append( "%c%s" % (  OutputRecManager.sep[2], varName ) )
                elif oRec.varList:
                   portData.append( "%s%c%d%c" % (  port_name, OutputRecManager.sep[2], nVarDims, OutputRecManager.sep[1]  ) )
                   for varRec in oRec.varList:
                        portData.append( "%c%s%c" % (  OutputRecManager.sep[2], varRec[0],  OutputRecManager.sep[3] ) )
                elif oRec.varComboList:
                   portData.append( "%s%c%d%c" % ( port_name, OutputRecManager.sep[2], nVarDims, OutputRecManager.sep[1]  ) )
                   for varName in oRec.getSelectedVariableList():
                       portData.append( "%c%s%c" % (  OutputRecManager.sep[2], varName,  OutputRecManager.sep[3] ) )               
                if ( oRec.levelsCombo <> None ):
                   portData.append( "%c%s" % ( OutputRecManager.sep[1], str( oRec.levelsCombo.currentText() )  ) )
        serializedData = ''.join( portData )
        print " -- PortData: %s " % serializedData
        return serializedData
    
###############################################################################   
         
class OutputRec:
    
    def __init__(self, name, **args ): 
        self.name = name
        self.varComboList = args.get( "varComboList", [] )
        self.levelsCombo = args.get( "levelsCombo", None )
        self.level = args.get( "level", None )
        self.varTable = args.get( "varTable", None )
        self.varList = args.get( "varList", None )
        self.varSelections = args.get( "varSelections", [] )
        self.type = args.get( "type", None )
        self.ndim = args.get( "ndim", 3 )
        self.updateSelections() 

    def getVarList(self):
        vlist = []
        for vrec in self.varList:
            vlist.append( str( getItem( vrec ) ) )
        return vlist
    
    def getSelectedVariableList(self):
        return [ str( varCombo.currentText() ) for varCombo in self.varComboList ]

    def getSelectedLevel(self):
        return str( self.levelsCombo.currentText() ) if self.levelsCombo else None
    
    def updateSelections(self):
        self.varSelections = []
        for varCombo in self.varComboList:
            varSelection = str( varCombo.currentText() ) 
            self.varSelections.append( [ varSelection, "" ] )

###############################################################################   

  
class ConfigurableFunction( QObject ):
    
    ConfigurableFunctions = {}    
    
    def __init__( self, name, function_args, key, **args ):
        QObject.__init__(self)
        self.name = name
        self.type = 'generic'
        self.args = function_args
        self.kwargs = args
        self.label = args.get( 'label', self.name )
        self.units = args.get( 'units', '' ).strip().lower()
        self.key = key
        self.functionID = -1 
        self.isLayerDependent = args.get( 'layerDependent', False )
        self.activeBound = args.get( 'activeBound', 'both' )
        self.active = args.get( 'active', True )
        self.activeFunctionList = []
        self.module = None
        self.altMode = False
#        self.parameterInputEnabled = True                                      # Handlers executed at:
        self.initHandler = args.get( 'init', None )         #    end of compute()
        self.openHandler = args.get( 'open', None )         #    key press
        self.startHandler = args.get( 'start', None )       #    left click
        self.updateHandler = args.get( 'update', None )     #    mouse drag or menu option choice
        self.hasState = args.get( 'hasState', True )
        
    def postInstructions( self, module, message ):
        print "\n ----- %s -------\n" % message

    @staticmethod
    def getActiveFunctionList( active_irens = None ):
        activeFunctionList = []
        for cfgFunctionMap in ConfigurableFunction.ConfigurableFunctions.values():
            for cfgFunction in cfgFunctionMap.values():
#                if cfgFunction.module and (  ( active_irens == None ) or ( cfgFunction.module.iren in active_irens ) ):
                activeFunctionList.append( cfgFunction )
        return activeFunctionList
    
    @staticmethod
    def clear():
        ConfigurableFunction.ConfigurableFunctions = {}
        print "clear"
         
    def updateActiveFunctionList( self ):
        from packages.vtDV3D.PersistentModule import PersistentVisualizationModule 
        cfgFunctGlobalMap = ConfigurableFunction.ConfigurableFunctions
        cfgFunctionMap = cfgFunctGlobalMap.get( self.name, {} )
        self.activeFunctionList = []
        valid_irens =  PersistentVisualizationModule.getValidIrens() 
#        print " ** N active_irens: %d " % len( active_irens )      
        for cfgFunction in cfgFunctionMap.values():
            if (cfgFunction <> self) and cfgFunction.module:
                isActive = ( cfgFunction.module.iren in valid_irens )
                if isActive and (cfgFunction.units == self.units):
                    self.activeFunctionList.append( cfgFunction )
             
    def matches( self, key ):
        return self.active and ( self.key == key )
    
    def applyParameter( self, module, **args ):
        pass

    def init( self, module ):
#        if self.name == 'colorScale':
#            print "."
        self.moduleID = module.moduleID
        self.module = module
        if ( self.initHandler != None ):
            self.initHandler( **self.kwargs ) 
        configFunctionMap = ConfigurableFunction.ConfigurableFunctions.setdefault( self.name, {} )
        configFunctionMap[self.module] = self

            
    def expandRange( self ):
        pass
            
#    def setParameterInputEnabled( self, isEnabled ):
#        self.parameterInputEnabled = isEnabled
            
    def getHelpText( self ):
        return "<tr>   <td>%s</td>  <td>%s</td> <td>%s</td> </tr>\n" % ( self.key, self.label, self.type )

    def open( self, state, alt = False ):
        if( self.name == state ): 
            self.altMode = alt
            if ( self.openHandler != None ): 
                self.openHandler()
            
    def close(self):
        pass
            
    def activateWidget( self, iren ):
        pass
    
    def reset(self):
        return None
        
    def start( self, state, x, y ):
        if ( self.startHandler != None ) and ( self.name == state ):
            self.startHandler( x, y )

    def update( self, state, x, y, wsize ):
        if ( self.updateHandler != None ) and ( self.name == state ):
            return self.updateHandler( x, y, wsize )
        return None
    
    def getTextDisplay(self, **args ):
        return None
    
    def wrapData( self, data ):
        wrappedData = []
        argClasses = iter( self.args )
        for data_elem in data:
            arg_sig = argClasses.next()
            arg_class = arg_sig[0] if IsListType( arg_sig ) else arg_sig
            wd_val = arg_class()
            wd_val.setValue( data_elem )
            wrappedData.append( wd_val )
        return wrappedData

    def unwrapData( self, data ):
        unwrappedData = []
        for data_elem in data:
            uw_val = data_elem.getResult()
            wrappedData.append( uw_val )
        return wrappedData
            
################################################################################


################################################################################

class WindowLevelingConfigurableFunction( ConfigurableFunction ):
    
    def __init__( self, name, key, **args ):
        ConfigurableFunction.__init__( self, name, [ ( Float, 'min'), ( Float, 'max'),  ( Integer, 'ctrl'), ( Float, 'refine0'), ( Float, 'refine1') ], key, **args  )
        self.type = 'leveling'
        self.manuallyAdjusted = False
        self.windowLeveler = QtWindowLeveler( **args )
        self.windowRefiner = WindowRefinementGenerator( range=[ 0.001, 0.999 ] )
        if( self.initHandler == None ): self.initHandler = self.initLeveling
        if( self.startHandler == None ): self.startHandler = self.startLeveling
        if( self.updateHandler == None ): self.updateHandler = self.updateLeveling
        self.setLevelDataHandler = args.get( 'setLevel', None )
        self.getLevelDataHandler = args.get( 'getLevel', None )
        self.getInitLevelDataHandler = args.get( 'getInitLevel', None )
        self.isDataValue = args.get( 'isDataValue', True )
        self.initial_range = args.get( 'initRange', None )
        self.initRefinement = args.get( 'initRefinement', [ 0.0, 1.0 ] )
        self.range_bounds = None
        self.boundByRange = args.get( 'bound', True )
        self.adjustRange = args.get( 'adjustRange', False )
        self.widget = args.get( 'gui', None )

    def postInstructions( self, module, message ):
        module.displayInstructions( message ) # "Left-click, mouse-move, left-click in this cell." )
    
    def applyParameter( self, module, **args ):
        try:
            self.setLevelDataHandler( self.range, **args )
        except Exception, err:
            print>>sys.stderr, "Error in setLevelDataHandler: ", str(err)
        print "Apply %s Parameter[%s:%d]: %s " % ( self.type, self.name, module.moduleID, str( self.range ) )
        if self.name == 'zScale':
            print "x"
        
    def reset(self):
        self.setLevelDataHandler( self.initial_range )
        self.module.render() 
        return self.initial_range

    def expandRange( self ):
        if self.adjustRange:
            if ( self.range_bounds[0] <> self.module.seriesScalarRange[0] ) or ( self.range_bounds[1] <> self.module.seriesScalarRange[1] ):
                self.range_bounds[0:2] = self.module.seriesScalarRange[0:2]
                self.initial_range[:] = self.range_bounds[:]
                if not self.manuallyAdjusted: 
                    self.range[0:2] = self.range_bounds[0:2]
                    self.initLeveling( initRange = False ) 
 
    def initLeveling( self, **args ):
        initRange = args.get( 'initRange', True )
        if initRange:
            if self.initial_range == None:
                self.initial_range =  [ 0.0, 1.0, 1 ] if ( self.getLevelDataHandler == None ) else self.getLevelDataHandler()
            if self.range_bounds == None:
                self.range_bounds = self.initial_range if ( self.getLevelDataHandler == None ) else self.getLevelDataHandler()
            self.range = list( self.module.getInputValue( self.name, self.initial_range ) if not self.module.newDataset else self.initial_range )
            if len( self.range ) == 3: 
                for iR in range(2): self.range.append( self.initRefinement[iR] )
        self.windowLeveler.setDataRange( self.range )
        self.setLevelDataHandler( self.range )
        self.module.setParameter( self.name, self.range )
        if self.widget: 
            self.widget.initLeveling( self.range )
            self.connect( self.widget, SIGNAL('update(QString)'), self.broadcastLevelingData )

        print "    ***** Init Leveling Parameter: %s, initial range = %s" % ( self.name, str(self.range) )
        
    def startLeveling( self, x, y ):
        if self.altMode:    self.windowRefiner.initRefinement( [ x, y ], self.range[3:5] )   
        else:               self.windowLeveler.startWindowLevel( x, y )
        self.updateActiveFunctionList()
        self.adjustRange = False
        self.emit(SIGNAL('startLeveling()'))
        print "startLeveling: %s " % str( self.range )

    def getTextDisplay(self, **args ):
        rmin = self.range[0] # if not self.isDataValue else self.module.getDataValue( self.range[0] )
        rmax = self.range[1] # if not self.isDataValue else self.module.getDataValue( self.range[1] )
        units = self.module.units if self.module else None
        if units: textDisplay = " Range: %.4G, %.4G %s . " % ( rmin, rmax, units )
        else: textDisplay = " Range: %.4G, %.4G . " % ( rmin, rmax )
        return textDisplay
    
    def updateWindow( self ): 
        self.windowLeveler.setWindowLevelFromRange( self.range )
            
    def updateLeveling( self, x, y, wsize ):
        if self.altMode:
            refinement_range = self.windowRefiner.updateRefinement( [ x, y ], wsize )
            for iR in [ 0, 1 ]: self.range[3+iR] = refinement_range[iR]
        else:  
            leveling_range = self.windowLeveler.windowLevel( x, y, wsize )
            for iR in [ 0, 1 ]: self.range[iR] = bound( leveling_range[iR], self.range_bounds ) if self.boundByRange else leveling_range[iR]
        self.emit( SIGNAL('updateLeveling()') )
        return self.broadcastLevelingData()
#        print "updateLeveling: %s " % str( self.range )

    def setImageDataRange(  self, imageRange  ):
        data_range = self.module.getDataValues( imageRange )
        self.range[0:2] = data_range[0:2]
        print " setImageDataRange, imageRange=%s, dataRange=%s " % ( str(imageRange), str(data_range) )
        self.setLevelDataHandler( self.range )
        
    def broadcastLevelingData(  self, range = None, **args  ):
        if range: self.range = range
#        print " ** Broadcast Leveling: altMode = %s, range = %s, refine = %s, Modules: " % ( str( self.altMode ) , str( self.range[0:2] ), str( self.range[3:5] )  )
        affected_renderers = set()
        active_module_list = args.get( 'active_modules', None )
        if (active_module_list == None) or (self.module in active_module_list):
            self.setLevelDataHandler( self.range )
            affected_renderers.add( self.module.renderer )
            self.manuallyAdjusted = True
#        print "   -> self = %x " % id(self.module)
        imageRange = self.module.getImageValues( self.range[0:2] ) 
        for cfgFunction in self.activeFunctionList:
            if (active_module_list == None) or (cfgFunction.module in active_module_list):
                cfgFunction.setImageDataRange( imageRange  )
                affected_renderers.add( cfgFunction.module.renderer )
#               print "   -> module = %x " % id(cfgFunction.module)

        for renderer in affected_renderers:
            if renderer <> None:
                rw = renderer.GetRenderWindow()
                if rw <> None: rw.Render()

        return self.range # self.wrapData( range )

################################################################################

class GuiConfigurableFunction( ConfigurableFunction ):
    
    start_parameter_signal = SIGNAL('start_parameter')
    update_parameter_signal = SIGNAL('update_parameter')
    finalize_parameter_signal = SIGNAL('finalize_parameter')
    
    def __init__( self, name, guiClass, key, **args ):
        ConfigurableFunction.__init__( self, name, guiClass.getSignature(), key, **args  )
        self.type = 'gui'
        self.guiClass = guiClass
        if( self.initHandler == None ): self.initHandler = self.initGui
        if( self.openHandler == None ): self.openHandler = self.openGui
        self.setValueHandler = args.get( 'setValue', None )
        self.getValueHandler = args.get( 'getValue', None )
        self.startConfigurationObserver = args.get( 'start', None )
        self.updateConfigurationObserver = args.get( 'update', None )
        self.finalizeConfigurationObserver = args.get( 'finalize', None )
        self.gui = None
        
    def initGui( self, **args ):
        if self.gui == None: 
            self.gui = self.guiClass.getInstance( self.guiClass, self.name, self.module, **args  )
            if self.startConfigurationObserver <> None:
                self.gui.connect( self.gui, self.start_parameter_signal, self.startConfigurationObserver )
            if self.updateConfigurationObserver <> None:
                self.gui.connect( self.gui, self.update_parameter_signal, self.updateConfigurationObserver )
            if self.finalizeConfigurationObserver <> None:
                self.gui.connect( self.gui, self.finalize_parameter_signal, self.finalizeConfigurationObserver )
        initial_value = None if ( self.getValueHandler == None ) else self.getValueHandler()          
        value = self.module.getInputValue( self.name, initial_value )  # if self.parameterInputEnabled else initial_value
        if value <> None: 
            self.gui.setValue( value )
            self.setValue( value )
            self.module.setResult( self.name, value )

    def openGui( self ):
        value = self.getValueHandler() if (self.getValueHandler <> None) else None 
        self.gui.initWidgetFields( value, self.module )
        self.gui.show()
        self.module.resetNavigation()
        
    def getTextDisplay(self, **args ):
        return self.gui.getTextDisplay( **args )
       
    def setValue( self, value ):
        if self.setValueHandler <> None: 
            self.setValueHandler( value )

################################################################################

class WidgetConfigurableFunction( ConfigurableFunction ):
        
    def __init__( self, name, signature, widgetWrapper, key, **args ):
        ConfigurableFunction.__init__( self, name, signature, key, **args  )
        self.type = 'widget'
        self.widget = None
        self.widgetWrapper = widgetWrapper
        if( self.initHandler == None ): self.initHandler = self.initWidget
        if( self.openHandler == None ): self.openHandler = self.openWidget
        self.setValueHandler = args.get( 'setValue', None )
        self.getValueHandler = args.get( 'getValue', None )
        
    def initWidget( self, **args ):
        if self.widget == None: self.widget = self.widgetWrapper( self.name, self.module, **args )
        initial_value = None if ( self.getValueHandler == None ) else self.getValueHandler() 
        value = self.module.getInputValue( self.name, initial_value ) # if self.parameterInputEnabled else initial_range
        if value <> None: 
            self.widget.setInitialValue( value )         
            self.setValue( value )
            self.module.setParameter( self.name, value )
                
    def reset(self):
        return self.widget.reset()
        
    def close(self):
        self.widget.close()

    def activateWidget( self, iren ):
        self.widget.activateWidget( iren )

    def openWidget( self ):
        start_value = None if ( self.getValueHandler == None ) else self.getValueHandler() 
        self.widget.open( start_value )
        self.module.resetNavigation()
        
    def getTextDisplay(self, **args ):
        return self.widget.getTextDisplay(**args)

    def setValue( self, value ):
        if self.setValueHandler <> None: 
            self.setValueHandler( value )
       
    def getValue( self ):
        if self.getValueHandler <> None: 
            return self.getValueHandler()
            
################################################################################

class ModuleDocumentationDialog( QDialog ):
    """
    ModuleDocumentationDialog is a dialog for showing module documentation.  It has a set of tabbed pages corresponding to a set of topics.

    """
    def __init__(self, useHTML=True, parent=None):
        QDialog.__init__(self, parent)
        self.textPages = {}
        self.useHTML = useHTML
        self.setWindowTitle('Module Documentation')
        self.setLayout(QVBoxLayout())
        self.layout().addStrut(600)
        self.closeButton = QPushButton('Ok', self)
        self.tabbedWidget = QTabWidget()
        self.layout().addWidget( self.tabbedWidget )         
        self.layout().addWidget(self.closeButton)
        self.connect(self.closeButton, SIGNAL('clicked(bool)'), self.close)
        self.closeButton.setShortcut('Enter')
        
    def addCloseObserver( self, observer ):
        self.connect(self.closeButton, SIGNAL('clicked(bool)'), observer )
    
    def getTabPage( self, name ): 
        tabPage = self.textPages.get( name, None ) 
        if tabPage == None:  
            textEdit = QTextEdit(self)
            textEdit.setReadOnly(True)
            index = self.tabbedWidget.addTab( textEdit, name ) 
            self.tabbedWidget.setCurrentWidget(textEdit)
            tabPage = [ textEdit, [] ]
            self.textPages[name] = tabPage
        return tabPage
    
    def clearTopic( self, topic ):
        tabPage = self.textPages.get( topic, None )
        if tabPage <> None: tabPage[1] = []
                                    
    def addDocument( self, topic, text ):
        tabPage = self.getTabPage( topic )
        tabPage[1].append( text )
        
    def generateDisplayedText(self):
        for tabPage in self.textPages.values():
            if self.useHTML:    tabPage[0].setHtml ( '\n<hr width="90%" color="#6699ff" size="6" />\n'.join( tabPage[1] ) )               
            else:               tabPage[0].setText ( '\n############################################################\n'.join( tabPage[1] ) )
        
    def clearDocuments(self):
        for tabPage in self.textPages.values():
            tabPage[1] = []
        
    def show(self):
        self.generateDisplayedText()
        QDialog.show(self)
        
#        self.textEdit.setTextCursor( QTextCursor(self.textEdit.document()) )   
        
 ################################################################################

class IVModuleConfigurationDialog( QWidget ):
    """
    IVModuleConfigurationDialog ...   
    """ 
    instances = {}
    activeModuleList = []
    update_animation_signal = SIGNAL('update_animation')      
         
    def __init__(self, name, **args ):
        QWidget.__init__(self, None)
        self.modules = OrderedDict()
        self.module = None
        self.initValue = None
        self.name = name
        title = ( '%s configuration' % name )
        self.setWindowTitle( title )        
        self.setLayout(QVBoxLayout())
        self.tabbedWidget = QTabWidget()
        self.layout().addWidget( self.tabbedWidget ) 
        self.layout().setMargin(5)
        self.layout().setSpacing(5)
        self.createContent()
        self.createButtonLayout()
        self.createActiveModulePanel()
        self.setWindowFlags( self.windowFlags() | Qt.WindowStaysOnTopHint )
        self.tabbedWidget.setCurrentIndex(0)
    
    @staticmethod    
    def getInstance( klass, name, caller, **args  ):
#        stack = inspect.stack()
#        frame = stack[0][0]
#        print " ---> %s: %s" % ( frame.__class__, dir( frame ) )
        instance = IVModuleConfigurationDialog.instances.setdefault( name, klass( name, **args )  )
        instance.addActiveModule( caller )
        return instance 
                              
    def createContent(self ):
        """ createContent() 
        Creates the content of this widget       
        """
        pass
    
    def addActiveModule( self, module ):
        if not module in self.modules:
            row = len( self.modules )
            activateCheckBox = QCheckBox( 'Activate' )
            activateCheckBox.setChecked( True )
            module_label = QLabel( module.getName()  )
            self.moduleTabLayout.addWidget( module_label, row, 0 )
            self.moduleTabLayout.addWidget( activateCheckBox, row, 1 )
            if not module in self.modules:
                if not ( self.activeModuleList and self.activeModuleList[-1] == module ):
                    self.activeModuleList.append( module )
                    self.connect( self, self.update_animation_signal, module.updateAnimation )
            self.modules[ module ] = activateCheckBox
            self.connect( activateCheckBox, SIGNAL( "stateChanged(int)" ), callbackWrapper( module.setActivation, self.name ) )  
            self.moduleTabLayout.update()
#            self.registerModule( module )
#            print "Add active module %s to dialog %s[%s], modules: %s" % ( module.getName(), self.name, str(id(self)), str(self.modules.keys() ) )
         
    def parameterUpdating(self):
        for module in self.modules:
            if self.modules[ module ].isChecked():
                if module.parameterUpdating( self.name ):
                    return True
        return False

    def updateConfiguration(self):
        for module in self.modules:
            if self.modules[ module ].isChecked() :
                module.updateConfigurationObserver( self.name, self.getValue() )        

    def initiateParameterUpdate(self):
        for module in self.modules:
            if self.modules[ module ].isChecked() :
                module.initiateParameterUpdate( self.name )
 
    def refreshPipeline(self):
        wmods = getWorkflowObjectMap()
        for module in self.modules:   
            wmod = wmods[ module.moduleID ]
            if wmod == None:
                executeWorkflow()
                return
            
    def resetNavigation(self):   
        for module in self.modules: 
            module.resetNavigation()
            
    def close(self):
        self.resetNavigation()  
        QWidget.close( self ) 
 
    def getTextDisplay( self, **args  ):
        value = self.getTextValue( self.getValue() )
        return "%s: %s" % ( self.name, value ) if value else None
       
    def getTextValue( self, value, **args ):
        text_value = None
        text_value_priority = 0
        for module in self.modules:
            if self.modules[ module ].isChecked() :
                tval, priority = module.getParameterDisplay( self.name, value )
                if tval and ( priority > text_value_priority ): 
                    text_value = tval
                    text_value_priority = priority
        return str( text_value ) if text_value else None
 
    def activateWidget( self, iren ):
        pass

    def initWidgetFields( self, value, module ):
        if ( self.module == None ) or ( module.renderer <> None ): 
            self.module = module
        self.initValue = value

    def createActiveModulePanel(self ):
        """ createEditor() -> None
        Configure sections       
        """       
        activeModuleTab = QWidget()        
        self.tabbedWidget.addTab( activeModuleTab, 'Active Modules' )
        self.tabbedWidget.setCurrentWidget(activeModuleTab)
        self.moduleTabLayout = QGridLayout()
        self.moduleTabLayout.setMargin( 5 )
        self.moduleTabLayout.setSpacing( 5 )
        activeModuleTab.setLayout( self.moduleTabLayout )
                      
#QLayout.removeItem (self, QLayoutItem)
#QLayout.count (self)
#QLayoutItem QLayout.itemAt (self, int index)
#QLayout.addItem (self, QLayoutItem)

#    def refreshActiveModules(self): 
#        layout = QGridLayout()
#        self.activeModuleTab.setLayout( layout ) 
#        layout.setMargin(10)
#        layout.setSpacing(20)
#        moduleIter = iter( self.modules )     
#        for iRow in range( len( self.modules ) ):
#            module = moduleIter.next()            
#            activateCheckBox = QCheckBox('Activate')
#            activateCheckBox.setChecked( self.modules[module] )
#            module_label = QLabel( module.getName()  )
#            layout.addWidget( module_label, iRow, 0 )
#            layout.addWidget( activateCheckBox, iRow, 1 )
#            self.connect( activateCheckBox, SIGNAL("stateChanged(int)"), self.updateActiveModules )  
#
#    def updateActiveModules( self, val ):
#        for item in self.modules.items():
#            active = item[1]
#            module = item[0]

    def createButtonLayout(self):
        """ createButtonLayout() -> None
        Construct Ok & Cancel button
        
        """
        self.buttonLayout = QHBoxLayout()
        self.buttonLayout.setMargin(5)
        self.okButton = QPushButton('&OK', self)
        self.okButton.setAutoDefault(False)
        self.okButton.setFixedWidth(100)
        self.buttonLayout.addWidget(self.okButton)
        self.cancelButton = QPushButton('&Cancel', self)
        self.cancelButton.setAutoDefault(False)
        self.cancelButton.setShortcut('Esc')
        self.cancelButton.setFixedWidth(100)
        self.buttonLayout.addWidget(self.cancelButton)
        self.layout().addLayout(self.buttonLayout)
        self.connect(self.okButton, SIGNAL('clicked(bool)'), self.okTriggered)
        self.connect(self.cancelButton, SIGNAL('clicked(bool)'), self.cancelTriggered)
                    
    def okTriggered(self, checked = False):
        """ okTriggered(checked: bool) -> None
        Update vistrail controller (if neccesssary) then close the widget        
        """
        self.finalizeParameter()
        self.close()

    def cancelTriggered(self, checked = False):
        self.close()
        
    def closeTriggered(self, checked = False):
        self.close()

    def finalizeParameter( self, *args ):
        self.emit( GuiConfigurableFunction.finalize_parameter_signal, self.name, self.getValue() )
        command = [ self.name ]
        value = self.getValue()
        command.extend( value )
        HyperwallManager.getInstance().processGuiCommand( command  )

    def startParameter( self, *args ):
        self.emit( GuiConfigurableFunction.start_parameter_signal, self.name, self.getValue() )

    def updateParameter( self, *args ):
        self.emit( GuiConfigurableFunction.update_parameter_signal, self.name, self.getValue() )

    @staticmethod   
    def getSignature( self ):
        return []
        
    def getValue( self ):
        return None

    def setValue( self, value ):
        pass

################################################################################
 
class IVModuleWidgetWrapper( QObject ):
    """
    IVModuleConfigurationDialog ...   
    """ 
       
    def __init__(self, name, module, **args ):
        QObject.__init__(self)
        self.name = name
        self.module = module
        self.initial_value = None
        self.current_value = None
#        self.configToParameterConversion = args.pop( 'configToParameter' )
#        self.parameterToConfigConversion = args.pop( 'parameterToConfig' )
        self.createContent( )
                              
    def createContent( self ):
        """ createContent() 
        Creates the content of this widget       
        """
        pass
    
    def getTextDisplay( self ):
        return "%s: %s" % ( self.name, str(self.getCurrentValue() ) )
 
    def activateWidget( self, iren ):
        pass
    
    def render(self):
        self.module.render()
           
    def close():
        pass 

    def open( start_value ):
        pass 
    
    def finalizeParameter( self, *args ):
        self.module.finalizeConfigurationObserver( self.name, *args )

    def startParameter( self, *args ):
        self.module.startConfigurationObserver( self.name, *args )

    def updateParameter( self, *args ):
        param_value = self.getValue()
        self.module.updateConfigurationObserver( self.name, param_value, *args )
        
    def getWidgetConfiguration( self ):
        return None
    
    def setInitialValue( self,  initial_value ):
        self.initial_value =  initial_value
        
    def getValue(self):
        self.current_value = self.getWidgetConfiguration() 
#        self.current_value = self.configToParameterConversion( config_value )
        return self.current_value

    def getCurrentValue(self):
        return self.current_value
        
    def reset(self):
        if self.initial_value <> None:
            self.setValue( self.initial_value )
        return self.initial_value 
            
    def setValue( self, parameter_value ):
        config_value = parameter_value # self.parameterToConfigConversion( parameter_value )
        self.setWidgetConfiguration( config_value )
        return config_value

    def setWidgetConfiguration( self, value ):
        pass

################################################################################
        
class ColormapConfigurationDialog( IVModuleConfigurationDialog ):   
    """
    ColormapConfigurationDialog ...   
    """ 
       
    def __init__(self, name, **args ):
        IVModuleConfigurationDialog.__init__( self, name, **args )
        
    @staticmethod   
    def getSignature():
        return [ (String, 'name'), ( Integer, 'invert'), ( Integer, 'stereo') ]
        
    def getValue(self):
        checkState = 1 if ( self.invertCheckBox.checkState() == Qt.Checked ) else 0
        stereoState = 1 if ( self.stereoCheckBox.checkState() == Qt.Checked ) else 0
        return [ str( self.colormapCombo.currentText() ), checkState, stereoState ]

    def setValue( self, value ):
        colormap_name = str( value[0] )
        check_state = Qt.Checked if int(float(value[1])) else Qt.Unchecked
        stereo_state = Qt.Checked if int(float(value[2])) else Qt.Unchecked
        itemIndex = self.colormapCombo.findText( colormap_name, Qt.MatchFixedString )
        if itemIndex >= 0: self.colormapCombo.setCurrentIndex( itemIndex )
        else: print>>sys.stderr, " Can't find colormap: %s " % colormap_name
        self.invertCheckBox.setCheckState( check_state )
        self.stereoCheckBox.setCheckState( stereo_state )
        
    def createContent(self ):
        """ createEditor() -> None
        Configure sections       
        """       
        colorMapTab = QWidget() 
        self.tabbedWidget.addTab( colorMapTab, 'Colormap' )                      
        self.tabbedWidget.setCurrentWidget(colorMapTab)
        layout = QGridLayout()
        colorMapTab.setLayout( layout ) 
        layout.setMargin(10)
        layout.setSpacing(20)
       
        colormap_label = QLabel( "Colormap:"  )
        layout.addWidget( colormap_label, 0, 0 ) 

        self.colormapCombo =  QComboBox ( self.parent() )
        colormap_label.setBuddy( self.colormapCombo )
        self.colormapCombo.setMaximumHeight( 30 )
        layout.addWidget( self.colormapCombo, 0,1 )
        for cmap in ColorMapManager.getColormaps(): self.colormapCombo.addItem( cmap )   
        self.connect( self.colormapCombo, SIGNAL("currentIndexChanged(QString)"), self.updateParameter )  
        
        self.invertCheckBox = QCheckBox('Invert')
        layout.addWidget( self.invertCheckBox, 1, 0 )
        self.connect( self.invertCheckBox, SIGNAL("stateChanged(int)"), self.updateParameter )  

        self.stereoCheckBox = QCheckBox('Stereo')
        layout.addWidget( self.stereoCheckBox, 1, 1 )
        self.connect( self.stereoCheckBox, SIGNAL("stateChanged(int)"), self.updateParameter )  

################################################################################
        
class LayerConfigurationDialog( IVModuleConfigurationDialog ):
    """
    LayerConfigurationDialog ...   
    """ 
       
    def __init__(self, name, **args ):
        IVModuleConfigurationDialog.__init__( self, name, **args )
        
    @staticmethod   
    def getSignature():
        return [ (String, 'layer'), ]
        
    def getValue(self):
        return [ str( self.layerCombo.currentText() ), ]

    def setValue( self, value ):
        if value:
            layer_name = str( value[0] )
            itemIndex = self.layerCombo.findText( layer_name, Qt.MatchFixedString )
            if itemIndex >= 0: self.layerCombo.setCurrentIndex( itemIndex )
            else: print>>sys.stderr, " Can't find colormap: %s " % layer_name

    def queryLayerList( self, ndims=3 ):
        portName = 'volume' if ( ndims == 3 ) else 'slice'
        mid = self.module.id
        while mid <> None:
            connectedModuleIds = getConnectedModuleIds( self.controller, mid, portName ) 
            for ( mid, mport ) in connectedModuleIds:
                module = self.controller.current_pipeline.modules[ mid ]
                dsetId = module.getAnnotation( "datasetId" )
                if dsetId:
                    portData = getFunctionParmStrValues( module, "portData" )
                    if portData:
                        serializedPortData = portData[0]
                        oRecMgr = OutputRecManager( serializedPortData )
                        orec = oRecMgr.getOutputRec( dsetId, portName )
                        return orec.getVarList()
        return []      
            
    def getLayerList( self ):
        for module in self.modules:
            layerList = module.getLayerList()
            if len(layerList): return layerList
        return []

    def initWidgetFields( self, value, module ):
        IVModuleConfigurationDialog.initWidgetFields( self, value, module )
        self.layerCombo.clear()
        layerlist = self.getLayerList()
        for layer in layerlist:
            if layer: self.layerCombo.addItem( layer ) 
                
    def createContent(self ):
        """ createEditor() -> None
        Configure sections       
        """       
        colorMapTab = QWidget() 
        self.tabbedWidget.addTab( colorMapTab, 'Layers' )                      
        self.tabbedWidget.setCurrentWidget(colorMapTab)
        layout = QGridLayout()
        colorMapTab.setLayout( layout ) 
        layout.setMargin(10)
        layout.setSpacing(20)
       
        layer_label = QLabel( "Layer:"  )
        layout.addWidget( layer_label, 0, 0 ) 

        self.layerCombo =  QComboBox ( self.parent() )
        layer_label.setBuddy( self.layerCombo )
        self.layerCombo.setMaximumHeight( 30 )
        layout.addWidget( self.layerCombo, 0, 1 ) 
        self.connect( self.layerCombo, SIGNAL("currentIndexChanged(QString)"), self.updateParameter )  

class DV3DConfigurationWidget(StandardModuleConfigurationWidget):
    
    newConfigurationWidget = None
    currentConfigurationWidget = None
    savingChanges = False

    def __init__(self, module, controller, title, parent=None):
        """ DV3DConfigurationWidget(module: Module,
                                       controller: VistrailController,
                                       parent: QWidget)
                                       -> LayerConfigurationWidget
        Setup the dialog ...
        
        """
        StandardModuleConfigurationWidget.__init__(self, module, controller, parent)
        self.setWindowTitle( title )
        self.moduleId = module.id
        self.pmod = self.module_descriptor.module.forceGetPersistentModule( module.id )
        self.getParameters( module )
        self.createTabs()
        self.createLayout()
        self.addPortConfigTab()
        if ( DV3DConfigurationWidget.newConfigurationWidget == None ): DV3DConfigurationWidget.setupSaveConfigurations() 
        DV3DConfigurationWidget.newConfigurationWidget = self 
        
    def destroy( self, destroyWindow = True, destroySubWindows = True):
        self.saveConfigurations()
        StandardModuleConfigurationWidget.destroy( self, destroyWindow, destroySubWindows )

#    def close (self):
#        pass
#        return StandardModuleConfigurationWidget.close(self)
    
    def sizeHint(self):
        return QSize(400,200)
    
    def createTabs( self ):
        self.setLayout( QVBoxLayout() )
        self.layout().setMargin(0)
        self.layout().setSpacing(0)

        self.tabbedWidget = QTabWidget()
        self.layout().addWidget( self.tabbedWidget ) 
        self.createButtonLayout() 
    
    def addPortConfigTab(self):
        portConfigPanel = self.getPortConfigPanel()
        self.tabbedWidget.addTab( portConfigPanel, 'ports' )           
        self.tabbedWidget.setCurrentWidget(portConfigPanel)
                 
    @staticmethod   
    def setupSaveConfigurations():
        import api
        ctrl = api.get_current_controller()
        scene = ctrl.current_pipeline_view
        scene.connect( scene, SIGNAL('moduleSelected'), DV3DConfigurationWidget.saveConfigurations )

    @staticmethod
    def saveConfigurations( newModuleId=None, selectedItemList=None ): 
        rv = False
        if not DV3DConfigurationWidget.savingChanges:
            if DV3DConfigurationWidget.currentConfigurationWidget and DV3DConfigurationWidget.currentConfigurationWidget.state_changed:
                rv = DV3DConfigurationWidget.currentConfigurationWidget.askToSaveChanges()
            DV3DConfigurationWidget.currentConfigurationWidget = DV3DConfigurationWidget.newConfigurationWidget
        return rv

    @staticmethod
    def saveNewConfigurations(): 
        rv = False
        if not DV3DConfigurationWidget.savingChanges:
            if DV3DConfigurationWidget.newConfigurationWidget and DV3DConfigurationWidget.newConfigurationWidget.state_changed:
                rv = DV3DConfigurationWidget.newConfigurationWidget.askToSaveChanges()
            DV3DConfigurationWidget.currentConfigurationWidget = DV3DConfigurationWidget.newConfigurationWidget
        return rv
        
#    def enterEvent(self, event):
##        print " ----------------------- enterEvent --------------------------------------"
#        self.mouseOver = True
#        QWidget.enterEvent(self, event)
#        
#    def leaveEvent(self, event):
##        print " ----------------------- leaveEvent --------------------------------------"
#        self.mouseOver = False
#        QWidget.leaveEvent(self, event)
        
#    def mousePressEvent (self, QMouseEvent):
#        print " ----------------------- mousePressEvent --------------------------------------"
#        print " MouseOver: %s "  % self.mouseOver
#        QWidget.mousePressEvent(self, event)

#    def focusInEvent(self, event):
#        print " ----------------------- focusInEvent --------------------------------------"
#        QWidget.focusInEvent(self, event)

#    def focusOutEvent(self, event):
##        print " ----------------------- focusOutEvent --------------------------------------"
#        if self.mouseOver:
#            event.ignore()
#        else:
#            self.askToSaveChanges()
#            QWidget.focusOutEvent(self, event)

    def getPortConfigPanel( self ):
        listContainer = QWidget( )
        listContainer.setLayout(QGridLayout(listContainer))
        listContainer.setFocusPolicy(Qt.WheelFocus)
        self.inputPorts = self.module.destinationPorts()
        self.inputDict = {}
        self.outputPorts = self.module.sourcePorts()
        self.outputDict = {}
        label = QLabel('Input Ports')
        label.setAlignment(Qt.AlignHCenter)
        label.font().setBold(True)
        label.font().setPointSize(12)
        listContainer.layout().addWidget(label, 0, 0)
        label = QLabel('Output Ports')
        label.setAlignment(Qt.AlignHCenter)
        label.font().setBold(True)
        label.font().setPointSize(12)
        listContainer.layout().addWidget(label, 0, 1)

        for i in xrange(len(self.inputPorts)):
            port = self.inputPorts[i]
            checkBox = self.checkBoxFromPort(port, True)
            checkBox.setFocusPolicy(Qt.StrongFocus)
            self.connect(checkBox, SIGNAL("stateChanged(int)"),
                         self.updateState)
            self.inputDict[port.name] = checkBox
            listContainer.layout().addWidget(checkBox, i+1, 0)
        
        for i in xrange(len(self.outputPorts)):
            port = self.outputPorts[i]
            checkBox = self.checkBoxFromPort(port)
            checkBox.setFocusPolicy(Qt.StrongFocus)
            self.connect(checkBox, SIGNAL("stateChanged(int)"),
                         self.updateState)
            self.outputDict[port.name] = checkBox
            listContainer.layout().addWidget(checkBox, i+1, 1)
        
        listContainer.adjustSize()
        listContainer.setFixedHeight(listContainer.height())
        return listContainer 

#
#        for i in xrange(len(self.inputPorts)):
#            port = self.inputPorts[i]
#            checkBox = self.checkBoxFromPort(port, True)
#            checkBox.setFocusPolicy(Qt.StrongFocus)
#            self.connect(checkBox, SIGNAL("stateChanged(int)"),
#                         self.updateState)
#            self.inputDict[port.name] = checkBox
#            listContainer.layout().addWidget(checkBox, i+1, 0)
#        
#        for i in xrange(len(self.outputPorts)):
#            port = self.outputPorts[i]
#            checkBox = self.checkBoxFromPort(port)
#            checkBox.setFocusPolicy(Qt.StrongFocus)
#            self.connect(checkBox, SIGNAL("stateChanged(int)"),
#                         self.updateState)
#            self.outputDict[port.name] = checkBox
#            listContainer.layout().addWidget(checkBox, i+1, 1)
#        
#        listContainer.adjustSize()
#        listContainer.setFixedHeight(listContainer.height())
#        return listContainer 
         
    def closeEvent(self, event):
        self.askToSaveChanges()
        w = self.getTopLevelWidget()
        w.close()
        
    def getTopLevelWidget(self):
        topWidget = self
        while True:
            w = topWidget.parentWidget()
            if w: topWidget = w
            else: return topWidget
        
    def updateState(self, state):
        self.setFocus(Qt.MouseFocusReason)
        self.saveButton.setEnabled(True)
        self.resetButton.setEnabled(True)
        if not self.state_changed:
            self.state_changed = True
            self.emit(SIGNAL("stateChanged"))
            
    def saveAndClose( self, checked = False ):
        self.saveTriggered( checked )
        self.close()

    def saveTriggered( self, checked = False ):
        self.okTriggered()
        for port in self.inputPorts:
            if (port.optional and
                self.inputDict[port.name].checkState()==Qt.Checked):
                self.module.visible_input_ports.add(port.name)
            else:
                self.module.visible_input_ports.discard(port.name)
            
        for port in self.outputPorts:
            if (port.optional and
                self.outputDict[port.name].checkState()==Qt.Checked):
                self.module.visible_output_ports.add(port.name)
            else:
                self.module.visible_output_ports.discard(port.name)
#        self.saveButton.setEnabled(False)
#        self.resetButton.setEnabled(False)
        self.state_changed = False
        self.emit(SIGNAL("stateChanged"))
        self.emit(SIGNAL('doneConfigure'), self.module.id)

        
#    def saveTriggered(self, checked = False):
#        self.okTriggered()
#        for port in self.inputPorts:
#            entry = (PortEndPoint.Destination, port.name)
#            if (port.optional and
#                self.inputDict[port.name].checkState()==Qt.Checked):
#                self.module.portVisible.add(entry)
#            else:
#                self.module.portVisible.discard(entry)
#            
#        for port in self.outputPorts:
#            entry = (PortEndPoint.Source, port.name)
#            if (port.optional and
#                self.outputDict[port.name].checkState()==Qt.Checked):
#                self.module.portVisible.add(entry)
#            else:
#                self.module.portVisible.discard(entry)
##        self.saveButton.setEnabled(False)
##        self.resetButton.setEnabled(False)
#        self.state_changed = False
#        self.emit(SIGNAL("stateChanged"))
#        self.emit(SIGNAL('doneConfigure'), self.module.id)

    def resetTriggered(self):
        self.setFocus(Qt.MouseFocusReason)
        self.setUpdatesEnabled(False)
        for i in xrange(len(self.inputPorts)):
            port = self.inputPorts[i]
            entry = (PortEndPoint.Destination, port.name)
            checkBox = self.inputDict[port.name]
            if not port.optional or entry in self.module.portVisible:
                checkBox.setCheckState(Qt.Checked)
            else:
                checkBox.setCheckState(Qt.Unchecked)
            if not port.optional or port.sigstring=='()':
                checkBox.setEnabled(False)
        for i in xrange(len(self.outputPorts)):
            port = self.outputPorts[i]
            entry = (PortEndPoint.Source, port.name)
            checkBox = self.outputDict[port.name]
            if not port.optional or entry in self.module.portVisible:
                checkBox.setCheckState(Qt.Checked)
            else:
                checkBox.setCheckState(Qt.Unchecked)
            if not port.optional:
                checkBox.setEnabled(False)
        self.setUpdatesEnabled(True)
#        self.saveButton.setEnabled(False)
#        self.resetButton.setEnabled(False)
        self.state_changed = False
        self.emit(SIGNAL("stateChanged"))
        self.close()
                
#    def resetTriggered(self):
#        self.setFocus(Qt.MouseFocusReason)
#        self.setUpdatesEnabled(False)
#        for i in xrange(len(self.inputPorts)):
#            port = self.inputPorts[i]
#            entry = (PortEndPoint.Destination, port.name)
#            checkBox = self.inputDict[port.name]
#            if not port.optional or entry in self.module.portVisible:
#                checkBox.setCheckState(Qt.Checked)
#            else:
#                checkBox.setCheckState(Qt.Unchecked)
#            if not port.optional or port.sigstring=='()':
#                checkBox.setEnabled(False)
#        for i in xrange(len(self.outputPorts)):
#            port = self.outputPorts[i]
#            entry = (PortEndPoint.Source, port.name)
#            checkBox = self.outputDict[port.name]
#            if not port.optional or entry in self.module.portVisible:
#                checkBox.setCheckState(Qt.Checked)
#            else:
#                checkBox.setCheckState(Qt.Unchecked)
#            if not port.optional:
#                checkBox.setEnabled(False)
#        self.setUpdatesEnabled(True)
##        self.saveButton.setEnabled(False)
##        self.resetButton.setEnabled(False)
#        self.state_changed = False
#        self.emit(SIGNAL("stateChanged"))
        
    def stateChanged(self, changed = True ):
        self.state_changed = changed
#        print " %s-> state changed: %s " % ( self.pmod.getName(), str(changed) )

    def getParameters( self, module ):
        pass

    def createLayout( self ):
        pass

    def createButtonLayout(self):
        """ createButtonLayout() -> None
        Construct Save & Reset button
        
        """
        self.buttonLayout = QHBoxLayout()
        self.buttonLayout.setMargin(5)
        self.saveButton = QPushButton('&Save', self)
        self.saveButton.setFixedWidth(100)
        self.saveButton.setEnabled(True)
        self.buttonLayout.addWidget(self.saveButton)
        self.resetButton = QPushButton('&Close', self)
        self.resetButton.setFixedWidth(100)
        self.resetButton.setEnabled(True)
        self.buttonLayout.addWidget(self.resetButton)
        
        self.layout().addLayout(self.buttonLayout)
        self.connect(self.saveButton,SIGNAL('clicked(bool)'),  self.saveAndClose )
        self.connect(self.resetButton,SIGNAL('clicked(bool)'),  self.close )
        self.setMouseTracking(True)
        self.setFocusPolicy( Qt.WheelFocus )
        
    def okTriggered(self):
        pass
       
    @staticmethod
    def readVariableList( dsId, cdmsFile ):
        vList = []
        try:
            if cdmsFile.strip():
                dataset = cdms2.open( cdmsFile ) 
                for var in dataset.variables:
                    vardata = dataset[var]
                    var_ndim = getVarNDim( vardata )
                    vList.append( ( '*'.join( [ dsId, var ] ), var_ndim ) ) 
                dataset.close()  
        except Exception, err:
            print>>sys.stderr, "Error reading variable list from dataset %s: %s " % ( cdmsFile, str(err) )
        return vList        

    @staticmethod
    def getTimeRange( mid ): 
        import api
        controller = api.get_current_controller()
        moduleId = mid
        datasetId = None
        timeRange = None
        while moduleId:
            connectedModuleIds = getConnectedModuleIds( controller, moduleId, 'dataset', True )
            for ( moduleId, portName ) in connectedModuleIds:
                module = controller.current_pipeline.modules[ moduleId ]
                datasetIdInput = getFunctionParmStrValues( module, "datasetId" )
                if datasetIdInput: 
                    datasetId = getItem( datasetIdInput )
                    datasetsInput = getFunctionParmStrValues( module, "datasets" )
                    if datasetsInput: 
                        timeRangeInput = getFunctionParmStrValues( module, "timeRange" )
                        if timeRangeInput: timeRange = [ int(timeRangeInput[0]), int(timeRangeInput[1]) ]
                        moduleId = None
        return ( datasetId, timeRange )

    @staticmethod
    def getDatasetMetadata( mid ): 
        import api
        controller = api.get_current_controller()
        datasetMap = {}
        moduleId = mid
        variableList = set()
        while moduleId <> None:
            connectedModuleIds = getConnectedModuleIds( controller, moduleId, 'dataset', True )
            for ( moduleId, portName ) in connectedModuleIds:
                module = controller.current_pipeline.modules[ moduleId ]
                datasetIdInput = getFunctionParmStrValues( module, "datasetId" )
                if datasetIdInput: 
                    datasetId = getItem( datasetIdInput )
                    datasetsInput = getFunctionParmStrValues( module, "datasets" )
                    if datasetsInput: 
                        datasets = deserializeStrMap( getItem( datasetsInput ) )
                        relFilePath = datasets[ datasetId ]
                        cdmsFile = getFullPath( relFilePath )
                        vlist = DV3DConfigurationWidget.readVariableList( datasetId, cdmsFile )
                        variableList.update( vlist )
                        timeRangeInput = getFunctionParmStrValues( module, "timeRange" )
                        timeRange = [ int(timeRangeInput[0]), int(timeRangeInput[1]) ] if timeRangeInput else None
                        datasetMap[ datasetId ] = (  variableList, cdmsFile, timeRange )
        for ( datasetId, dsetData ) in datasetMap.items():
            variableList = dsetData[0]
            moduleId = mid
            while moduleId <> None:
                connectedModuleIds = getConnectedModuleIds( controller, moduleId, 'dataset', True )
                for ( moduleId, portName ) in connectedModuleIds:
                    module = controller.current_pipeline.modules[ moduleId ]
                    taskInput = getFunctionParmStrValues( module, "task" )
                    if taskInput:
                        taskMapInput = deserializeTaskData( getItem( taskInput ) ) 
                        if taskMapInput:
                            taskMap = taskMapInput       
                            taskRecord = taskMap.get( datasetId, None )
                            if taskRecord:
                                outputs = taskRecord[2].split(';')
                                for output in outputs:
                                    outputData = output.split('#')
                                    if len(outputData) > 1:
                                        variableList.add( ( outputData[1], int( outputData[2] ) ) )
        return datasetMap

    @staticmethod
    def getVariableList( mid ): 
        import api
        from packages.vtDV3D.CDMS_DatasetReaders import CDMSDatasetRecord   
        controller = api.get_current_controller()
        moduleId = mid
        cdmsFile = None
        datasetIds = set()
        timeRange = None
        selected_var = None
        levelsAxis = None
        variableList = set()
        moduleIdList = [ moduleId ]
        while moduleIdList:
            connectedModuleIds = getConnectedModuleIds( controller, moduleIdList.pop(), 'dataset', True )
            for ( moduleId, portName ) in connectedModuleIds:
                module = controller.current_pipeline.modules[ moduleId ]
                datasetsInput = getFunctionParmStrValues( module, "datasets" )
                moduleIdList.append( moduleId )
                if datasetsInput:
                    datasets = deserializeStrMap( getItem( datasetsInput ) )
                    for datasetId in datasets:
                        relFilePath = datasets[ datasetId ]
                        if relFilePath:
                            cdmsFile = getFullPath( relFilePath )
                            vlist = DV3DConfigurationWidget.readVariableList( datasetId, cdmsFile )
                            variableList.update( vlist )
                            timeRangeInput = getFunctionParmStrValues( module, "timeRange" )
                            if timeRangeInput: timeRange = [ int(timeRangeInput[0]), int(timeRangeInput[1]) ]
                            gridInput = getFunctionParmStrValues( module, "grid" )
                            if gridInput: 
                                selected_var = getItem( gridInput ) 
                                if selected_var:
                                    referenceData = selected_var.split('*')
                                    refDsid = referenceData[0]
                                    refVar  = referenceData[1].split(' ')[0]                                
                                    relFilePath = datasets[ refDsid ]
                                    cdmsFile = getFullPath( relFilePath )
                                    dataset = cdms2.open( cdmsFile ) 
                                    levelsAxis=dataset[refVar].getLevel()
                            datasetIds.add( datasetId )
        moduleIdList.append( mid )
        datasetId = '-'.join( datasetIds )
        while moduleIdList:
            connectedModuleIds = getConnectedModuleIds( controller, moduleIdList.pop(), 'dataset', True )
            for ( moduleId, portName ) in connectedModuleIds:
                module = controller.current_pipeline.modules[ moduleId ]
                moduleIdList.append( moduleId )
                taskInput = getFunctionParmStrValues( module, "task" )
                if taskInput:
                    taskMapInput = deserializeTaskData( getItem( taskInput ) ) 
                    if taskMapInput:
                        taskMap = taskMapInput       
                        taskRecord = taskMap.get( datasetId, None )
                        if taskRecord:
                            outputs = taskRecord[2].split(';')
                            for output in outputs:
                                outputData = output.split('#')
                                if len(outputData) > 1:
                                    variableList.add( ( outputData[1], int( outputData[2] ) ) )
        return ( variableList, datasetId, timeRange, selected_var, levelsAxis )


#    def persistParameter( self, parameter_name, output, **args ):
#        self.pmod.persistParameter( parameter_name, output, **args )
#        self.pmod.persistVersionMap() 

    def persistParameterList( self, parameter_list, **args ):
        self.pmod.persistParameterList( parameter_list, **args )
                        
    def queryLayerList( self, ndims=3 ):
        portName = 'volume' if ( ndims == 3 ) else 'slice'
        mid = self.module.id
        while mid <> None:
            connectedModuleIds = getConnectedModuleIds( self.controller, mid, portName ) 
            for ( mid, mport ) in connectedModuleIds:
                module = self.controller.current_pipeline.modules[ mid ]
                dsetIdData = getFunctionParmStrValues( module, "datasetId" )
                if dsetIdData:
                    dsetId = dsetIdData[0]
                    portData = getFunctionParmStrValues( module, "portData" )
                    if portData:
                        serializedPortData = portData[0]
                        oRecMgr = OutputRecManager( serializedPortData )
                        orec = oRecMgr.getOutputRec( dsetId, portName )
                        return orec.getVarList()
        return []        
        
    def checkBoxFromPort(self, port, input_=False):
        checkBox = QCheckBox(port.name)
        if input_:
            port_visible = port.name in self.module.visible_input_ports
        else:
            port_visible = port.name in self.module.visible_output_ports
        if not port.optional or port_visible:
            checkBox.setCheckState(Qt.Checked)
        else:
            checkBox.setCheckState(Qt.Unchecked)
        if not port.optional or (input_ and port.sigstring=='()'):
            checkBox.setEnabled(False)
        return checkBox
               
################################################################################
        
class AnimationConfigurationDialog( IVModuleConfigurationDialog ):
    """
    AnimationConfigurationDialog ...   
    """ 
   
    def __init__(self, name, **args):
        self.iTimeStep = 0
        self.relTimeStart = None
        self.relTimeStep = 1.0
        self.maxSpeedIndex = 100
        self.maxDelaySec = args.get( "maxDelaySec", 1.0 )
        self.running = False
        self.timeRange = None
        self.datasetId = None
        self.timer = QTimer()
        self.timer.connect( self.timer, SIGNAL('timeout()'), self.animate )
        self.timer.setSingleShot( True )
        IVModuleConfigurationDialog.__init__( self, name, **args )
                                  
    @staticmethod   
    def getSignature():
        return [ ( Float, 'timeValue'), ]
        
    def getValue(self):
        return [ self.iTimeStep ]

    def setValue( self, value ):
        iTS = getItem( value )
        if self.timeRange and ( ( iTS >= self.timeRange[1] ) or  ( iTS < self.timeRange[0] ) ): iTS = self.timeRange[0]
        self.iTimeStep = iTS
                
#    def loadAnimation(self):
#        self.getTimeRange(  )
#        for iTS in range( self.timeRange[0], self.timeRange[1] ):
#            self.setTimestep( iTS ) 
#            time.sleep( 0.01 ) 
#            if not self.running: break
                
    def step( self ):
        if not self.running:
            self.updateTimeRange()
            self.setTimestep( self.iTimeStep + 1 )

    def reset( self ):
        if self.running:
            self.runButton.setText('Run')
            self.running = False
        self.setTimestep(0)

    def getTimeRange( self ): 
#        wmods = getWorkflowObjectMap()
        for module in self.modules: 
            timeRangeInput =  module.getCachedParameter( "timeRange" )
            if timeRangeInput: 
                self.timeRange = [ int(timeRangeInput[0]), int(timeRangeInput[1]) ]
                self.relTimeStart = float( timeRangeInput[2] )
                self.relTimeStep = float( timeRangeInput[3] )
                return

    def setTimestep( self, iTimestep ):
        from packages.vtDV3D.PersistentModule import ReferenceTimeUnits 
        if self.timeRange[0] == self.timeRange[1]:
            self.running = False
        else:
            try:
                self.setValue( iTimestep )
                sheetTabs = set()
                relTimeValueRef = self.relTimeStart + self.iTimeStep * self.relTimeStep
                timeAxis = self.module.getMetadata('time')
                timeValues = np.array( object=timeAxis.getValue() )
                relTimeRef = cdtime.reltime( relTimeValueRef, ReferenceTimeUnits )
                relTime0 = relTimeRef.torel( timeAxis.units )
                timeIndex = timeValues.searchsorted( relTime0.value ) 
                if ( timeIndex >= len( timeValues ) ): timeIndex = len( timeValues ) - 1
                relTimeValue0 =  timeValues[ timeIndex ]
                r0 = cdtime.reltime( relTimeValue0, timeAxis.units )
                relTimeRef = r0.torel( ReferenceTimeUnits )
                relTimeValueRefAdj = relTimeRef.value
                print " ** Update Animation, timestep = %d, timeValue = %.3f, timeRange = %s " % ( self.iTimeStep, relTimeValueRefAdj, str( self.timeRange ) )
                displayText = self.getTextDisplay()
                HyperwallManager.getInstance().processGuiCommand( ['reltimestep', relTimeValueRefAdj, displayText ], False  )
                for module in self.activeModuleList:
                    dvLog( module, " ** Update Animation, timestep = %d " % ( self.iTimeStep ) )
                    module.updateAnimation( relTimeValueRefAdj, displayText  )
            except Exception:
                traceback.print_exc( 100, sys.stderr )
#                print>>sys.stdout, "Error in setTimestep[%d]: %s " % ( iTimestep, str(err) )

    def stop(self):
        self.runButton.setText('Run')
        self.running = False 
        for module in self.activeModuleList:
            module.stopAnimation()

    def cancelTriggered(self, checked = False):
        self.stop()
        IVModuleConfigurationDialog.cancelTriggered( self, checked )
        
    def updateTimeRange(self):   
        newConfig = DV3DConfigurationWidget.saveConfigurations()
        if newConfig or not self.relTimeStart: self.getTimeRange()

    def start(self):
        self.updateTimeRange()
        self.runButton.setText('Stop')
        self.running = True
        self.timer.start()       
        
    def run( self ): 
        if self.running: self.stop()           
        else: self.start()
        
#            self.runButton.setText('Stop')
#            executeWorkflow()
#            self.getTimeRange()
#            if inGuiThread:
#                self.animate()
#            else:
#            self.running = True
#            self.loadAnimation()
#            self.getTimeRange()
#            self.runButton.setDisabled(True)
#            self.setValue( 0 )
#            self.timer.start()
#            self.runThread = threading.Thread( target=self.animate )
#            self.runThread.start()
             
    def animate(self):
        self.setTimestep( self.iTimeStep + 1 )  
        if self.running: 
            delayTime = ( self.maxSpeedIndex - self.speedSlider.value() + 1 ) * self.maxDelaySec * ( 1000.0 /  self.maxSpeedIndex )
            print " Animate step, delay time = %.2f msec" % delayTime
            self.timer.start( delayTime ) 
                
#    def run1(self):
#        if self.running:
#            self.runButton.setText('Run')
#            self.running = False
#        else:
#            self.runButton.setText('Stop')
#            executeWorkflow()
#            self.running = True
#            self.runThread = threading.Thread( target=self.animate )
#            self.runThread.start()
#     
#        
#    def animate1(self):
#        refresh = True
#        while self.running:
#            self.initiateParameterUpdate()
#            self.setTimestep( self.iTimeStep + 1, refresh )
#            while self.parameterUpdating():
#                time.sleep(0.01)
#            delayTime =  ( self.maxSpeedIndex - self.speedSlider.value() + 1 ) * self.delayTimeScale    
#            time.sleep( delayTime ) 
#            refresh = False
##            printTime( 'Finish Animation delay' )
                
#    def setDelay( self, dval  ):
#        dval = 
#        self.delay = delay_in_sec if ( delay_in_sec<>None ) else self.speedSlider.value()/100.0
        
        
    def createContent(self ):
        """ createEditor() -> None
        Configure sections       
        """       
        animMapTab = QWidget()        
        self.tabbedWidget.addTab( animMapTab, 'Animation' )                                       
        self.tabbedWidget.setCurrentWidget(animMapTab)
        layout = QVBoxLayout()
        animMapTab.setLayout( layout ) 
        layout.setMargin(10)
        layout.setSpacing(20)
       
        label_layout = QHBoxLayout()
        label_layout.setMargin(5)
        anim_label = QLabel( "Speed:"  )
        label_layout.addWidget( anim_label  ) 
        self.speedSlider = QSlider( Qt.Horizontal )
        self.speedSlider.setRange( 0, self.maxSpeedIndex )
        self.speedSlider.setSliderPosition( self.maxSpeedIndex )
#        self.connect(self.speedSlider, SIGNAL('valueChanged()'), self.setDelay )
        anim_label.setBuddy( self.speedSlider )
        label_layout.addWidget( self.speedSlider  ) 
        
        layout.addLayout( label_layout )
        
        self.buttonLayout = QHBoxLayout()
        self.buttonLayout.setMargin(5)
        layout.addLayout(self.buttonLayout)
        
        self.runButton = QPushButton( 'Run', self )
        self.runButton.setAutoDefault(False)
        self.runButton.setFixedWidth(100)
        self.buttonLayout.addWidget(self.runButton)
        self.connect(self.runButton, SIGNAL('clicked(bool)'), self.run )

        self.stepButton = QPushButton( 'Step', self )
        self.stepButton.setAutoDefault(False)
        self.stepButton.setFixedWidth(100)
        self.buttonLayout.addWidget(self.stepButton)
        self.connect(self.stepButton, SIGNAL('clicked(bool)'), self.step )

        self.resetButton = QPushButton( 'Reset', self )
        self.resetButton.setAutoDefault(False)
        self.resetButton.setFixedWidth(100)
        self.buttonLayout.addWidget(self.resetButton)
        self.connect(self.resetButton, SIGNAL('clicked(bool)'), self.reset )

class LevelConfigurationDialog( IVModuleConfigurationDialog ):
    """
    LevelConfigurationDialog ...   
    """ 
   
    def __init__(self, name, **args):
        self.datasetId = None
        self.activeModule = None
        self.levelsCombo  = None
        IVModuleConfigurationDialog.__init__( self, name, **args )
                                  
    @staticmethod   
    def getSignature():
        return [ ( Float, 'levelValue'), ]
    
    def finalizeParameter(self):
        self.setLevel()
        IVModuleConfigurationDialog.finalizeParameter(self)
        
    def getValue( self ):
        return str( self.levelsCombo.currentText() )
                       
    def setLevel( self ):
        levValue = self.getValue()
        self.module.setCurrentLevel( levValue )
        textDisplay = "%s: %s" % ( self.name, levValue )
        for module in self.activeModuleList:
            module.dvUpdate( animate=True ) 
            module.updateTextDisplay( textDisplay ) 
        
    def updateLayout(self):
        if self.levelsCombo.count() == 0:
            levels = self.module.lev.getValue()
            for level in levels: self.levelsCombo.addItem( str(level) )
            self.levelsCombo.update()
        
    def showEvent ( self, event ):
        self.updateLayout()
        IVModuleConfigurationDialog.showEvent( self, event )
                                  
    def createContent(self ):
        """ createEditor() -> None
        Configure sections       
        """       
        levelMapTab = QWidget()        
        self.tabbedWidget.addTab( levelMapTab, 'Levels' )                                       
        self.tabbedWidget.setCurrentWidget(levelMapTab)
        layout = QVBoxLayout()
        levelMapTab.setLayout( layout ) 
        layout.setMargin(10)
        layout.setSpacing(20)
        
        self.levelsCombo = QComboBox()
        layout.addWidget( self.levelsCombo )
        
#        self.buttonLayout = QHBoxLayout()
#        self.buttonLayout.setMargin(5)
#        layout.addLayout(self.buttonLayout)
#        
#        self.setButton = QPushButton( 'Set Level', self )
#        self.setButton.setAutoDefault(False)
#        self.setButton.setFixedWidth(100)
#        self.buttonLayout.addWidget(self.setButton)
#        self.connect(self.setButton, SIGNAL('clicked(bool)'), self.setLevel )

#        self.stepButton = QPushButton( 'Step Level', self )
#        self.stepButton.setAutoDefault(False)
#        self.stepButton.setFixedWidth(100)
#        self.buttonLayout.addWidget(self.stepButton)
#        self.connect(self.stepButton, SIGNAL('clicked(bool)'), self.step )

#        self.cancelButton = QPushButton( 'Cancel', self )
#        self.cancelButton.setAutoDefault(False)
#        self.cancelButton.setFixedWidth(100)
#        self.buttonLayout.addWidget(self.cancelButton)
#        self.connect(self.cancelButton, SIGNAL('clicked(bool)'), self.cancelLevel )

#class LayerConfigurationDialog( IVModuleConfigurationDialog ):
#    """
#    LayerConfigurationDialog ...   
#    """    
#    def __init__(self, name, **args):
#        self.activeLayer = False
#        IVModuleConfigurationDialog.__init__( self, name, **args )
#                
#    @staticmethod   
#    def getSignature():
#        return [ ( String, 'layer'), ]
#        
#    def getValue(self):
#        return [ self.activeLayer ]
#
#    def setValue( self, value ):
#        self.activeLayer = getItem( value ) 
#        
#    def createContent(self ):
#        """ createEditor() -> None
#        Configure sections       
#        """       
#        layerTab = QWidget()        
#        self.tabbedWidget.addTab( layerTab, 'Layers' )                                       
#        layersLayout = QVBoxLayout()
#        layerTab.setLayout( layersLayout ) 
#        layersLayout.setMargin(10)
#        layersLayout.setSpacing(20)
#                               
#        layer_selection_Layout = QHBoxLayout()      
#        layer_selection_label = QLabel( "Select Layer:"  )
#        layer_selection_Layout.addWidget( layer_selection_label ) 
#        self.layersCombo =  QComboBox ( self )
#        layer_selection_label.setBuddy( self.layersCombo )
##        layersCombo.setMaximumHeight( 30 )
#        layer_selection_Layout.addWidget( self.layersCombo ) 
#        
#        for layer in self.layerList:               
#            self.layersCombo.addItem( str(layer) ) 
#        
#        if self.layer:
#            currentLayerIndex = self.layersCombo.findText ( self.layer )   
#            if currentLayerIndex >= 0: self.layersCombo.setCurrentIndex( currentLayerIndex ) 
# 
#        layersLayout.addLayout( layer_selection_Layout )

                
class LayerConfigurationWidget(DV3DConfigurationWidget):
    """
    LayerConfigurationWidget ...
    
    """
    def __init__(self, module, controller, parent=None):
        """ LayerConfigurationWidget(module: Module,
                                       controller: VistrailController,
                                       parent: QWidget)
                                       -> LayerConfigurationWidget
        Setup the dialog ...
        
        """
        self.layer = None
        DV3DConfigurationWidget.__init__(self, module, controller, 'Layer Configuration', parent) 
        
    def getParameters( self, module ):
        self.layerList = self.queryLayerList()
        layerData = getFunctionParmStrValues( module, "layer" )
        if layerData: self.layer = layerData[0]
                               
    def createLayout(self):
        """ createEditor() -> None
        Configure sections
        
        """
        layersTab = QWidget()        
        self.tabbedWidget.addTab( layersTab, 'Layers' ) 
        self.tabbedWidget.setCurrentWidget(layersTab)
        layersLayout = QVBoxLayout()                
        layersTab.setLayout( layersLayout )
                               
        layer_selection_Layout = QHBoxLayout()      
        layer_selection_label = QLabel( "Select Layer:"  )
        layer_selection_Layout.addWidget( layer_selection_label ) 
        self.layersCombo =  QComboBox ( self )
        layer_selection_label.setBuddy( self.layersCombo )
#        layersCombo.setMaximumHeight( 30 )
        layer_selection_Layout.addWidget( self.layersCombo ) 
        
        for layer in self.layerList:               
            self.layersCombo.addItem( str(layer) ) 
        
        if self.layer:
            currentLayerIndex = self.layersCombo.findText ( self.layer )   
            if currentLayerIndex >= 0: self.layersCombo.setCurrentIndex( currentLayerIndex ) 
 
        layersLayout.addLayout( layer_selection_Layout )

    def updateController(self, controller):
        new_layer_value = str( self.layersCombo.currentText() )
        if new_layer_value <> self.layer: 
#            if self.pmod: self.pmod.changeVersion( self.layer, new_layer_value )
            self.persistParameterList( [ ('layer', [ new_layer_value, ]) ] )  
            self.layer = new_layer_value
        self.stateChanged(False)
          
    def okTriggered(self, checked = False):
        """ okTriggered(checked: bool) -> None
        Update vistrail controller (if neccesssary) then close the widget
        
        """
        self.updateController(self.controller)
        self.emit(SIGNAL('doneConfigure()'))
        self.close() 
        
ConfigCommandPopupManager = ConfigPopupManager()   


    
    
    
