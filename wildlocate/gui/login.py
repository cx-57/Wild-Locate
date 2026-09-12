"""Sign-in screen for the local account prototype."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout

from wildlocate.core.accounts import authenticate
from wildlocate.gui.widgets import BrandMark, app_icon, label


class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Wild-Locate · Welcome')
        self.setWindowIcon(app_icon())
        self.resize(510, 610)
        self.creating = False
        self.username = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(38, 32, 38, 32)
        outer.setSpacing(22)
        brand = QHBoxLayout()
        brand.addWidget(BrandMark())
        brand.addWidget(label('Wild-Locate', 'brand'))
        brand.addStretch()
        outer.addLayout(brand)
        self.title = label('Welcome back.', 'heading')
        outer.addWidget(self.title)
        outer.addWidget(label('Sign in to start exploring wildlife habitat.', 'muted', True))
        card = QFrame()
        card.setObjectName('card')
        body = QVBoxLayout(card)
        body.setContentsMargins(24, 24, 24, 24)
        body.setSpacing(12)
        self.name = QLineEdit()
        self.name.setMaxLength(40)
        self.name.setPlaceholderText('Your username')
        self.password = QLineEdit()
        self.password.setMaxLength(256)
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText('Your password')
        self.confirm = QLineEdit()
        self.confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm.setMaxLength(256)
        self.confirm.setPlaceholderText('Enter your password again')
        for title, field in [('Username', self.name), ('Password', self.password)]:
            caption = label(title, 'fieldLabel')
            caption.setBuddy(field)
            body.addWidget(caption)
            body.addWidget(field)
        self.confirm.setAccessibleName('Confirm password')
        body.addWidget(self.confirm)
        self.confirm.hide()
        self.error = label('', 'error', True)
        self.error.hide()
        body.addWidget(self.error)
        self.submit = QPushButton('Sign in')
        self.submit.setObjectName('primary')
        self.submit.setDefault(True)
        self.submit.clicked.connect(self.sign_in)
        body.addWidget(self.submit)
        self.switch = QPushButton('New here? Create an account')
        self.switch.setAutoDefault(False)
        self.switch.setObjectName('link')
        self.switch.clicked.connect(self.toggle_mode)
        body.addWidget(self.switch)
        outer.addWidget(card)
        outer.addWidget(label('Accounts stay on this computer. Models you train belong to your account. Bundled models and habitat data are available to everyone.', 'small', True))
        outer.addStretch()

    def toggle_mode(self):
        self.creating = not self.creating
        self.title.setText('Create your account.' if self.creating else 'Welcome back.')
        self.submit.setText('Create account' if self.creating else 'Sign in')
        self.switch.setText('Already have an account? Sign in' if self.creating else 'New here? Create an account')
        self.confirm.setVisible(self.creating)
        self.password.clear()
        self.confirm.clear()
        self.error.hide()

    def sign_in(self):
        try:
            if self.creating and self.password.text() != self.confirm.text():
                raise ValueError('Your passwords don’t match.')
            self.username = authenticate(self.name.text(), self.password.text(), create=self.creating)
        except ValueError as exc:
            self.error.setText(str(exc))
            self.error.show()
            return
        except Exception:
            self.error.setText('We couldn’t open the local account store. Please try again.')
            self.error.show()
            return
        self.password.clear()
        self.confirm.clear()
        self.accept()
