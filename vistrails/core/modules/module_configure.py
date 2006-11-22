from PyQt4 import QtCore, QtGui
from core.utils import any
from core.modules.module_registry import registry, ModuleRegistry
from core.vistrail.action import ChangeParameterAction
import urllib

class StandardModuleConfigurationWidget(QtGui.QDialog):

    def __init__(self, module, parent=None):
        QtGui.QDialog.__init__(self, parent)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowMinMaxButtonsHint)
        self.module = module
        self.moduleThing = registry.getDescriptorByName(self.module.name).module


class DefaultModuleConfigurationWidget(StandardModuleConfigurationWidget):

    def __init__(self, module, parent=None):
        StandardModuleConfigurationWidget.__init__(self, module, parent)
        self.setWindowTitle('Module Configuration')
        self.setLayout(QtGui.QVBoxLayout())
        self.layout().setMargin(0)
        self.layout().setSpacing(0)
        self.scrollArea = QtGui.QScrollArea(self)
        self.layout().addWidget(self.scrollArea)
        self.scrollArea.setFrameStyle(QtGui.QFrame.NoFrame)
        self.listContainer = QtGui.QWidget(self.scrollArea)
        self.listContainer.setLayout(QtGui.QGridLayout(self.listContainer))
        self.inputPorts = self.module.destinationPorts()
        self.inputDict = {}
        self.outputPorts = self.module.sourcePorts()
        self.outputDict = {}
        self.constructList()
        self.buttonLayout = QtGui.QHBoxLayout()
        self.buttonLayout.setMargin(5)
        self.okButton = QtGui.QPushButton('&OK', self)
        self.okButton.setFixedWidth(100)
        self.buttonLayout.addWidget(self.okButton)
        self.cancelButton = QtGui.QPushButton('&Cancel', self)
        self.cancelButton.setShortcut('Esc')
        self.cancelButton.setFixedWidth(100)
        self.buttonLayout.addWidget(self.cancelButton)
        self.layout().addLayout(self.buttonLayout)
        self.connect(self.okButton, QtCore.SIGNAL('clicked(bool)'), self.okTriggered)
        self.connect(self.cancelButton, QtCore.SIGNAL('clicked(bool)'), self.close)

    def checkBoxFromPort(self, port, input=False):
        checkBox = QtGui.QCheckBox(port.name)
        if not port.optional or port.name in self.module.portVisible:
            checkBox.setCheckState(QtCore.Qt.Checked)
        else:
            checkBox.setCheckState(QtCore.Qt.Unchecked)
        if not port.optional or (input and port.getSignatures()==['()']):
            checkBox.setEnabled(False)
        return checkBox

    def constructList(self):
        label = QtGui.QLabel('Input Ports')
        label.setAlignment(QtCore.Qt.AlignHCenter)
        label.font().setBold(True)
        label.font().setPointSize(12)
        self.listContainer.layout().addWidget(label, 0, 0)
        label = QtGui.QLabel('Output Ports')
        label.setAlignment(QtCore.Qt.AlignHCenter)
        label.font().setBold(True)
        label.font().setPointSize(12)
        self.listContainer.layout().addWidget(label, 0, 1)

        for i in range(len(self.inputPorts)):
            port = self.inputPorts[i]
            checkBox = self.checkBoxFromPort(port, True)
            self.inputDict[port.name] = checkBox
            self.listContainer.layout().addWidget(checkBox, i+1, 0)
        
        for i in range(len(self.outputPorts)):
            port = self.outputPorts[i]
            checkBox = self.checkBoxFromPort(port)
            self.outputDict[port.name] = checkBox
            self.listContainer.layout().addWidget(checkBox, i+1, 1)
        
        self.listContainer.adjustSize()
        self.listContainer.setFixedHeight(self.listContainer.height())
        self.scrollArea.setWidget(self.listContainer)
        self.scrollArea.setWidgetResizable(True)

    def sizeHint(self):
        return QtCore.QSize(384, 512)

    def okTriggered(self, checked = False):
        for i in range(len(self.inputPorts)):
            port = self.inputPorts[i]
            if port.optional and self.inputDict[port.name].checkState()==QtCore.Qt.Checked:
                self.module.portVisible.add(port.name)
            else:
                self.module.portVisible.discard(port.name)
            
        for i in range(len(self.outputPorts)):
            port = self.outputPorts[i]
            if port.optional and self.outputDict[port.name].checkState()==QtCore.Qt.Checked:
                self.module.portVisible.add(port.name)
            else:
                self.module.portVisible.discard(port.name)
        self.emit(QtCore.SIGNAL('updatePipeline()'))
        self.close()
        

class PortTable(QtGui.QTableWidget):
    def __init__(self, parent=None):
        QtGui.QTableWidget.__init__(self,1,2,parent)
        self.horizontalHeader().setResizeMode(QtGui.QHeaderView.Interactive)
        self.horizontalHeader().setMovable(False)
        self.horizontalHeader().setStretchLastSection(True)
        self.setSelectionMode(QtGui.QAbstractItemView.NoSelection)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.delegate = PortTableItemDelegate(self)
        self.setItemDelegate(self.delegate)
        self.setFrameStyle(QtGui.QFrame.NoFrame)
        self.connect(self.model(),
                     QtCore.SIGNAL('dataChanged(QModelIndex,QModelIndex)'),
                     self.handleDataChanged)

    def sizeHint(self):
        return QtCore.QSize()

    def fixGeometry(self):
        rect = self.visualRect(self.model().index(self.rowCount()-1,
                                                  self.columnCount()-1))
        self.setFixedHeight(self.horizontalHeader().height()+
                            rect.y()+rect.height()+1)

    def handleDataChanged(self, topLeft, bottomRight):
        if topLeft.column()==0:
            text = str(self.model().data(topLeft, QtCore.Qt.DisplayRole).toString())
            changedGeometry = False
            if text!='' and topLeft.row()==self.rowCount()-1:
                self.setRowCount(self.rowCount()+1)
                changedGeometry = True
            if text=='' and topLeft.row()<self.rowCount()-1:
                self.removeRow(topLeft.row())
                changedGeometry = True
            if changedGeometry:
                self.fixGeometry()

    def initializePorts(self, ports):
        self.disconnect(self.model(),
                        QtCore.SIGNAL('dataChanged(QModelIndex,QModelIndex)'),
                        self.handleDataChanged)
        for p in ports[0][1]:
            assert(len(p.spec)==1 and len(p.spec[0])==1)
            model = self.model()
            portType = registry.getDescriptorByThing(p.spec[0][0][0]).name
            model.setData(model.index(self.rowCount()-1, 1),
                          QtCore.QVariant(portType),
                          QtCore.Qt.DisplayRole)
            model.setData(model.index(self.rowCount()-1, 0),
                          QtCore.QVariant(p.name),
                          QtCore.Qt.DisplayRole)
            self.setRowCount(self.rowCount()+1)
        self.fixGeometry()
        self.connect(self.model(),
                     QtCore.SIGNAL('dataChanged(QModelIndex,QModelIndex)'),
                     self.handleDataChanged)
            

class PortTableItemDelegate(QtGui.QItemDelegate):

    def createEditor(self, parent, option, index):
        if index.column()==1: #Port type
            combo = QtGui.QComboBox(parent)
            combo.setEditable(False)
            for m in sorted(registry.moduleName.itervalues()):
                combo.addItem(m)
            return combo
        else:
            return QtGui.QItemDelegate.createEditor(self, parent, option, index)

    def setEditorData(self, editor, index):
        if index.column()==1:
            text = index.model().data(index, QtCore.Qt.DisplayRole).toString()
            editor.setCurrentIndex(editor.findText(text))
        else:
            QtGui.QItemDelegate.setEditorData(self, editor, index)

    def setModelData(self, editor, model, index):
        if index.column()==1:
            model.setData(index, QtCore.QVariant(editor.currentText()), QtCore.Qt.DisplayRole)
        else:
            QtGui.QItemDelegate.setModelData(self, editor, model, index)

class PythonHighlighter(QtGui.QSyntaxHighlighter):
    def __init__( self, document ):
        QtGui.QSyntaxHighlighter.__init__( self, document )
        self.rules = []
        literalFormat = QtGui.QTextCharFormat()
        literalFormat.setForeground(QtGui.QColor(65, 105, 225)) #royalblue
        self.rules += [(r"^[^']*'", 0, literalFormat, 1, -1)]
        self.rules += [(r"'[^']*'", 0, literalFormat, -1, -1)]
        self.rules += [(r"'[^']*$", 0, literalFormat, -1, 1)]
        self.rules += [(r"^[^']+$", 0, literalFormat, 1, 1)]        
        self.rules += [(r'^[^"]*"', 0, literalFormat, 2, -1)]
        self.rules += [(r'"[^"]*"', 0, literalFormat, -1, -1)]
        self.rules += [(r'"[^"]*$', 0, literalFormat, -1, 2)]
        self.rules += [(r'^[^"]+$', 0, literalFormat, 2, 2)]
        
        keywordFormat = QtGui.QTextCharFormat()
        keywordFormat.setForeground(QtCore.Qt.blue)
        self.rules += [(r"\b%s\b"%w, 0, keywordFormat, -1, -1)
                       for w in ["def","class","from", 
                                 "import","for","in", 
                                 "while","True","None",
                                 "False","pass","return",
                                 "self","tuple","list",
                                 "print","if","else",
                                 "elif","in","len",
                                 "assert","try","except",
                                 "exec", "break", "continue"
                                 "not", "and", "or"
                                 ]]
        
        defclassFormat = QtGui.QTextCharFormat()
        defclassFormat.setForeground(QtCore.Qt.blue)
        self.rules += [(r"\bdef\b\s*(\w+)", 1, defclassFormat, -1, -1)]
        self.rules += [(r"\bclass\b\s*(\w+)", 1, defclassFormat, -1, -1)]
        
        commentFormat = QtGui.QTextCharFormat()
        commentFormat.setFontItalic(True)
        commentFormat.setForeground(QtCore.Qt.darkGreen)
        self.rules += [(r"#[^\n]*", 0, commentFormat, -1, -1)]
        
    def highlightBlock(self, text):
        baseFormat = self.format(0)
        prevState = self.previousBlockState()
        self.setCurrentBlockState(prevState)
        for rule in self.rules:
            if prevState==rule[3] or rule[3]==-1:
                expression = QtCore.QRegExp(rule[0])
                pos = expression.indexIn(text, 0)
                while pos != -1:
                    pos = expression.pos(rule[1])
                    length = expression.cap(rule[1]).length()
                    if self.format(pos)==baseFormat:
                        self.setFormat(pos, length, rule[2])
                        self.setCurrentBlockState(rule[4])
                        pos = expression.indexIn(text, pos+expression.matchedLength())
                    else:
                        pos = expression.indexIn(text, pos+1)
                

class PythonEditor(QtGui.QTextEdit):

    def __init__(self, parent=None):
        QtGui.QTextEdit.__init__(self, parent)
        self.setLineWrapMode(QtGui.QTextEdit.NoWrap)
        self.setTabStopWidth(4)
        self.setFontFamily('Courier')
        self.setFontPointSize(10.0)
        self.highlighter = PythonHighlighter(self.document())
        self.connect(self,
                     QtCore.SIGNAL('currentCharFormatChanged(QTextCharFormat)'),
                     self.formatChanged)

    def formatChanged(self, f):
        self.setFontFamily('Courier')
        self.setFontPointSize(10.0)        
                 
class PythonSourceConfigurationWidget(StandardModuleConfigurationWidget):

    def __init__(self, module, parent=None):
        StandardModuleConfigurationWidget.__init__(self, module, parent)
        self.setWindowTitle('PythonSource Configuration')
        self.setLayout(QtGui.QVBoxLayout())
        self.layout().setMargin(0)
        self.layout().setSpacing(0)
        self.createPortTable()
        self.createEditor()
        self.createButtonLayout()        

    def createPortTable(self):
        self.inputPortTable = PortTable(self)
        labels = QtCore.QStringList() << "Input Port Name" << "Type"
        self.inputPortTable.setHorizontalHeaderLabels(labels)
        self.outputPortTable = PortTable(self)
        labels = QtCore.QStringList() << "Output Port Name" << "Type"
        self.outputPortTable.setHorizontalHeaderLabels(labels)
        if self.module.registry:
            iPorts = self.module.registry.destinationPorts(self.moduleThing)
            self.inputPortTable.initializePorts(iPorts)
            oPorts = self.module.registry.sourcePorts(self.moduleThing)
            self.outputPortTable.initializePorts(oPorts)
        self.layout().addWidget(self.inputPortTable)
        self.layout().addWidget(self.outputPortTable)
        self.performPortConnection(self.connect)

    def findSourceFunction(self):
        fid = -1
        for i in range(self.module.getNumFunctions()):
            if self.module.functions[i].name=='source':
                fid = i
                break
        return fid

    def createEditor(self):
        self.codeEditor = PythonEditor(self)
        fid = self.findSourceFunction()
        if fid!=-1:
            f = self.module.functions[fid]
            self.codeEditor.setPlainText(urllib.unquote(f.params[0].strValue))
        self.codeEditor.document().setModified(False)
        self.layout().addWidget(self.codeEditor, 1)

    def createButtonLayout(self):
        self.buttonLayout = QtGui.QHBoxLayout()
        self.buttonLayout.setMargin(5)
        self.okButton = QtGui.QPushButton('&OK', self)
        self.okButton.setFixedWidth(100)
        self.buttonLayout.addWidget(self.okButton)
        self.cancelButton = QtGui.QPushButton('&Cancel', self)
        self.cancelButton.setShortcut('Esc')
        self.cancelButton.setFixedWidth(100)
        self.buttonLayout.addWidget(self.cancelButton)
        self.layout().addLayout(self.buttonLayout)
        self.connect(self.okButton, QtCore.SIGNAL('clicked(bool)'), self.okTriggered)
        self.connect(self.cancelButton, QtCore.SIGNAL('clicked(bool)'), self.close)

    def sizeHint(self):
        return QtCore.QSize(512, 512)

    def performPortConnection(self, operation):
        operation(self.inputPortTable.horizontalHeader(),
                        QtCore.SIGNAL('sectionResized(int,int,int)'),
                        self.portTableResize)
        operation(self.outputPortTable.horizontalHeader(),
                  QtCore.SIGNAL('sectionResized(int,int,int)'),
                  self.portTableResize)

    def portTableResize(self, logicalIndex, oldSize, newSize):
        self.performPortConnection(self.disconnect)
        if self.inputPortTable.horizontalHeader().sectionSize(logicalIndex)!=newSize:
            self.inputPortTable.horizontalHeader().resizeSection(logicalIndex,newSize)
        if self.outputPortTable.horizontalHeader().sectionSize(logicalIndex)!=newSize:
            self.outputPortTable.horizontalHeader().resizeSection(logicalIndex,newSize)
        self.performPortConnection(self.connect)

    def newInputOutputPorts(self):
        ports = []
        for i in range(self.inputPortTable.rowCount()):
            model = self.inputPortTable.model()
            name = str(model.data(model.index(i, 0), QtCore.Qt.DisplayRole).toString())
            typeName = str(model.data(model.index(i, 1), QtCore.Qt.DisplayRole).toString())
            if name!='' and typeName!='':
                ports.append(('input', name, '('+typeName+')'))
        for i in range(self.outputPortTable.rowCount()):
            model = self.outputPortTable.model()
            name = str(model.data(model.index(i, 0), QtCore.Qt.DisplayRole).toString())
            typeName = str(model.data(model.index(i, 1), QtCore.Qt.DisplayRole).toString())
            if name!='' and typeName!='':
                ports.append(('output', name, '('+typeName+')'))
        return ports

    def specsFromPorts(self, portType, ports):
        return [(portType,
                 p.name,
                 '('+registry.getDescriptorByThing(p.spec[0][0][0]).name+')')
                for p in ports[0][1]]

    def registryChanges(self, oldRegistry, newPorts):
        if oldRegistry:
            oldIn = self.specsFromPorts('input',
                                        oldRegistry.destinationPorts(self.moduleThing))
            oldOut = self.specsFromPorts('output',
                                         oldRegistry.sourcePorts(self.moduleThing))
        else:
            oldIn = []
            oldOut = []
        deletePorts = [p for p in oldIn if not p in newPorts]
        deletePorts += [p for p in oldOut if not p in newPorts]
        addPorts = [p for p in newPorts if ((not p in oldIn) and (not p in oldOut))]
        return (deletePorts, addPorts)

    def updateActionsHandler(self, controller):
        oldRegistry = self.module.registry
        newPorts = self.newInputOutputPorts()
        (deletePorts, addPorts) = self.registryChanges(oldRegistry, newPorts)
        for (cid, c) in controller.currentPipeline.connections.items():
            if ((c.sourceId==self.module.id and
                 any([c.source.name==p[1] for p in deletePorts])) or
                (c.destinationId==self.module.id and
                 any([c.destination.name==p[1] for p in deletePorts]))):
                controller.deleteConnection(cid)
        for p in deletePorts:
            controller.deleteModulePort(self.module.id, p)
        for p in addPorts:
            controller.addModulePort(self.module.id, p)
        if self.codeEditor.document().isModified():
            code = urllib.quote(str(self.codeEditor.toPlainText()))
            fid = self.findSourceFunction()
            if fid==-1:
                fid = self.module.getNumFunctions()
            action = ChangeParameterAction()
            action.addParameter(self.module.id, fid, 0, 'source',
                                '<no description>',code,'String', '')
            controller.performAction(action)
        
    def okTriggered(self, checked = False):
        self.emit(QtCore.SIGNAL('updateActions'), self.updateActionsHandler)
        self.emit(QtCore.SIGNAL('updatePipeline()'))
        self.close()
