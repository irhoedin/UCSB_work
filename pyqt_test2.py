import sys
from PyQt4 import QtGui

class Example(QtGui.QWidget):
    def __init__(self):
        super(Example, self).__init__()
        self.initUI()
        
    def initUI(self):
        title = QtGui.QLabel('Title')
        author = QtGui.QLabel('Author')
        review = QtGui.QLabel('Review')

        titleEdit = QtGui.QLineEdit()
        authorEdit = QtGui.QLineEdit()
        reviewEdit = QtGui.QLineEdit()

        grid = QtGui.QVBoxLayout()

        self.groupBox = QtGui.QGroupBox("Header")
        orivbox = QtGui.QVBoxLayout()

        layout1 = QtGui.QHBoxLayout()
        layout1.addWidget(title)
        layout1.addWidget(titleEdit)

        layout2 = QtGui.QHBoxLayout()
        layout2.addWidget(author)
        layout2.addWidget(authorEdit)

        orivbox.addLayout(layout1)
        orivbox.addLayout(layout2)

        self.groupBox.setLayout(orivbox)
        grid.addWidget(self.groupBox)

        self.groupBox2 = QtGui.QGroupBox("Main")
        mainbox = QtGui.QVBoxLayout()
        mainbox.addWidget(review)
        mainbox.addWidget(reviewEdit)
        self.groupBox2.setLayout(mainbox)
        grid.addWidget(self.groupBox2)
        
        self.setLayout(grid) 
        self.setGeometry(300, 300, 350, 300)
        self.setWindowTitle('Group box sample')    
        self.show()
        
def main():
    app = QtGui.QApplication(sys.argv)
    ex = Example()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
