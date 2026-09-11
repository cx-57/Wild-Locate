STYLESHEET = """
QWidget { font-family: 'Segoe UI'; font-size: 13px; color: #233c34; }
QMainWindow, QScrollArea, QWidget#canvas, QWidget#page { background: #f5f6f2; }
QScrollArea { border: 0; }
QWidget#nav { background: #f5f6f2; border-bottom: 1px solid #dde3da; }
QLabel { background: transparent; border: none; }
QLabel#brand { font-size: 22px; font-weight: 650; letter-spacing: -0.7px; }
QLabel#eyebrow { font-size: 10px; font-weight: 600; letter-spacing: 2px; color: #627b6e; }
QLabel#hero { font-family: 'Georgia'; font-size: 41px; color: #193e30; }
QLabel#description { font-size: 14px; color: #66756c; }
QLabel#heading { font-size: 20px; font-weight: 600; letter-spacing: -0.4px; }
QLabel#subheading { font-size: 15px; font-weight: 600; }
QLabel#muted { color: #69776e; font-size: 12px; }
QLabel#small { color: #718075; font-size: 11px; }
QLabel#fieldLabel { font-size: 12px; font-weight: 600; color: #42594d; }
QLabel#step { font-size: 10px; font-weight: 600; letter-spacing: 1.3px; color: #77867a; }
QLabel#pill { background: #e7eee5; color: #3e6550; border: 1px solid #d8e4d5; border-radius: 12px; padding: 5px 11px; font-size: 10px; font-weight: 600; letter-spacing: 0.8px; }
QLabel#category { background: #e9f0dd; color: #426139; border-radius: 10px; padding: 6px 11px; font-size: 10px; font-weight: 600; letter-spacing: 1px; }
QLabel#error { color: #963f32; background: #fcf0eb; border: 1px solid #efd7ce; border-radius: 8px; padding: 12px; }
QLabel#notice { color: #607165; background: #f0f3ec; border-radius: 8px; padding: 12px; font-size: 11px; }
QLabel#percentile { color: #204b37; font-size: 67px; font-weight: 500; letter-spacing: -3px; }
QLabel#emptyHeading { color: #355944; font-family: 'Georgia'; font-size: 27px; }
QFrame#card { background: #ffffff; border: 1px solid #dfe5dc; border-radius: 14px; }
QFrame#divider { background: #e6ebe3; border: none; min-height: 1px; max-height: 1px; }
QFrame#environment, QFrame#methodology { background: #ffffff; border: 1px solid #dfe5dc; border-radius: 12px; }
QComboBox, QLineEdit { background: #fbfcf9; border: 1px solid #d4ded2; border-radius: 7px; padding: 12px 11px; min-height: 20px; selection-background-color: #285a40; }
QComboBox { padding-right: 32px; }
QComboBox:hover, QLineEdit:hover { border-color: #9bad98; }
QComboBox:focus, QLineEdit:focus { border: 2px solid #477c54; padding: 11px 10px; }
QComboBox:disabled, QLineEdit:disabled { color: #8a958d; background: #f4f6f1; border-color: #e3e8df; }
QLineEdit[invalid="true"] { border: 1px solid #b75742; background: #fff8f4; }
QComboBox::drop-down { border: none; width: 28px; }
QAbstractItemView#speciesSuggestions { background: white; border: 1px solid #d4ded2; padding: 0; selection-background-color: #e8efdf; selection-color: #193e30; outline: none; }
QAbstractItemView#speciesSuggestions::item { min-height: 22px; padding: 8px 12px; }
QPushButton { background: transparent; border: 1px solid transparent; border-radius: 7px; padding: 9px 12px; font-weight: 500; }
QPushButton:hover { background: #eaf0e5; }
QPushButton:focus { border: 1px solid #477c54; }
QPushButton#primary { background: #254f38; color: #ffffff; font-size: 14px; font-weight: 600; padding: 14px 16px; }
QPushButton#primary:hover { background: #326647; }
QPushButton#primary:pressed { background: #193e2a; }
QPushButton#primary:disabled { color: #d4dfce; background: #718974; }
QPushButton#secondary { border: 1px solid #d5dfcf; color: #42634b; }
QPushButton#link { color: #47724f; font-size: 11px; padding: 5px 0px; text-align: left; }
QPushButton#accordion { text-align: left; padding: 18px 21px; font-size: 13px; font-weight: 600; }
QPushButton:disabled { color: #8e9a8b; }
QProgressBar { background: #e5ecdf; border: none; border-radius: 2px; max-height: 4px; min-height: 4px; }
QProgressBar::chunk { background: #73945b; border-radius: 2px; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 4px 0px; }
QScrollBar::handle:vertical { background: #c6d1bf; border-radius: 4px; min-height: 35px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QToolTip { background: #234633; color: #ffffff; border: none; padding: 8px; }
"""
