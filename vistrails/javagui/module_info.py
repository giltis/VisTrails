from java.lang import Integer
from javax.swing import Box, BoxLayout, JComponent, JLabel, JPanel, JTextField
from java.awt import Dimension
from com.vlsolutions.swing.docking import DockKey, Dockable

from ports_pane import JPortsPane
from utils import InputValidationListener


class JModuleInfo(JComponent, Dockable):
    def __init__(self):
        super(JModuleInfo, self).__init__()
        self._module = None
        self._controller = None

        self._key = DockKey('module_info')

        self.setLayout(BoxLayout(self, BoxLayout.PAGE_AXIS))

        name_line = JPanel()
        name_line.setLayout(BoxLayout(name_line, BoxLayout.LINE_AXIS))
        name_line.add(JLabel("Name:"))
        self._name_input = JTextField()
        self._name_input.setMaximumSize(Dimension(
                Integer.MAX_VALUE,
                self._name_input.getPreferredSize().height))
        name_listener = InputValidationListener(self._name_validation)
        self._name_input.addKeyListener(name_listener)
        self._name_input.addFocusListener(name_listener)
        name_line.add(self._name_input)
        self.add(name_line)

        type_line = JPanel()
        type_line.setLayout(BoxLayout(type_line, BoxLayout.LINE_AXIS))
        type_line.add(JLabel("Type: "))
        self._type_label = JLabel()
        type_line.add(self._type_label)
        type_line.add(Box.createHorizontalGlue())
        self.add(type_line)

        pkg_line = JPanel()
        pkg_line.setLayout(BoxLayout(pkg_line, BoxLayout.LINE_AXIS))
        pkg_line.add(JLabel("Package: "))
        self._pkg_label = JLabel()
        pkg_line.add(self._pkg_label)
        pkg_line.add(Box.createHorizontalGlue())
        self.add(pkg_line)

        self._ports_pane = JPortsPane()
        self.add(self._ports_pane)

        self.add(Box.createVerticalGlue())

    def update_module(self, module=None):
        self._module = module

        self._ports_pane.update_module(module)

        if module is None:
            self._name_input.setText('')
            self._type_label.setText('')
            self._pkg_label.setText('')
        else:
            if module.has_annotation_with_key('__desc__'):
                label = module.get_annotation_by_key('__desc__').value.strip()
            else:
                label = ''
            self._name_input.setText(label)
            self._type_label.setText(module.name)
            self._pkg_label.setText(module.package)

    def _name_validation(self):
        if self._module is not None:
            old_text = ''
            if self._module.has_annotation_with_key('__desc__'):
                old_text = self._module.get_annotation_by_key('__desc__').value
            new_text = (self._name_input.getText()).strip()
            if not new_text:
                if old_text:
                    self._controller.delete_annotation('__desc__',
                                                      self._module.id)
            elif old_text != new_text:
                self._controller.add_annotation(('__desc__', new_text),
                                               self._module.id)

            # TODO : update pipeline view, if it can display names

    def _get_controller(self):
        return self._controller
    def _set_controller(self, controller):
        self._controller = controller
        self._ports_pane.controller = controller
    controller = property(_get_controller, _set_controller)

    # @Override
    def getDockKey(self):
        return self._key

    # @Override
    def getComponent(self, *args):
        if len(args) == 0:
            return self
        else:
            return JComponent.getComponent(self, *args)