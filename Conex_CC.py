#Connex.py
__author__ = 'Hidenori Nakayama'
__version__ = '1.0'


import visa
import sys
from PyQt4 import QtGui, QtCore

conex_adrs ='ASRL1::INSTR'

class Conex(object):

    def connect_module(self, adrs):
        
        rm = visa.ResourceManager('/Library/Frameworks/Visa.framework/VISA')
        self.cnx = rm.open_resource(adrs)
        self.cnx.baud_rate = 921600

        outp = self.cnx.query('1VE?')

        if 'CONEX-CC' in outp:
            print 'connected'

        else:
            print 'no connection'

    def homing(self):
        self.cnx.write('1OR')
        print 'homing, wait until the motion stops'

    def set_parms(self, accelaration, velocity, travel_len, zero_pos):
        """set parameters

        Args:
        accelaration: string, >1E-6 and <1E12
        velocity: string, >1E-6 and <1E12
        travel_len: string
        zero_pos: string
        """

        self.accelaration = accelaration
        self.velocity = velocity
        self.travel_len = travel_len
        self.zero_pos = zero_pos

        self.cnx.write('1AC' + self.accelaration)
        self.cnx.write('1VA' + self.velocity)
    
    def run(self):
        self.cnx.write('1PR' + self.travel_len)


    def back(self):
        self.cnx.write('1PA' + self.zero_pos)


class GUI(QtGui.QWidget, Conex):
    def __init__(self):
        super(GUI, self).__init__()
        self.initUI()

    
    def initUI(self):

        self.connect_btn = QtGui.QPushButton('CONNECT')
        self.connect_btn.setSizePolicy(QtGui.QSizePolicy.Preferred,
                    QtGui.QSizePolicy.Preferred)
        self.connect_btn.clicked.connect(self.connect_clicked)

        self.accl = QtGui.QLabel('ACCL')
        self.vel = QtGui.QLabel('VEL')
        self.lng = QtGui.QLabel('LNG')
        self.zero = QtGui.QLabel('ZERO')

        self.acclEdit = QtGui.QLineEdit()
        self.velEdit = QtGui.QLineEdit()
        self.lngEdit = QtGui.QLineEdit()
        self.zeroEdit = QtGui.QLineEdit()

        self.set_btn = QtGui.QPushButton('SET')
        self.set_btn.setSizePolicy(QtGui.QSizePolicy.Preferred,
                    QtGui.QSizePolicy.Preferred)
        self.set_btn.clicked.connect(self.set_clicked)

        self.run_btn = QtGui.QPushButton('RUN')
        self.run_btn.setSizePolicy(QtGui.QSizePolicy.Preferred,
                    QtGui.QSizePolicy.Preferred)
        self.run_btn.clicked.connect(self.run_clicked)

        self.back_btn = QtGui.QPushButton('BACK')
        self.back_btn.setSizePolicy(QtGui.QSizePolicy.Preferred,
                    QtGui.QSizePolicy.Preferred)
        self.back_btn.clicked.connect(self.back_clicked)


        self.box1 = QtGui.QVBoxLayout()
        self.box1.addWidget(self.connect_btn)

        #parmeter gird
        self.grid = QtGui.QGridLayout()

        self.grid.setSpacing(10)

        self.grid.addWidget(self.accl, 1, 0)
        self.grid.addWidget(self.acclEdit, 1, 1)

        self.grid.addWidget(self.vel, 1, 2)
        self.grid.addWidget(self.velEdit, 1, 3)
        
        self.grid.addWidget(self.lng, 2, 0)
        self.grid.addWidget(self.lngEdit, 2, 1)
        
        self.grid.addWidget(self.zero, 2, 2)
        self.grid.addWidget(self.zeroEdit, 2, 3)
        
        self.box1.addLayout(self.grid)

        #set button
        self.box1.addWidget(self.set_btn)

        #run and back
        self.box2 = QtGui.QHBoxLayout()
        self.box2.addWidget(self.run_btn)
        self.box2.addWidget(self.back_btn)

        self.box1.addLayout(self.box2)
        

        self.setLayout(self.box1)

        self.setGeometry(300, 399, 350, 300)
        self.setWindowTitle('CONEX-CC Interface by NORI')
        self.show()

    def connect_clicked(self):
        self.connect_module(conex_adrs)
        self.homing()

    def set_clicked(self):
        accl_read = str(self.acclEdit.text())
        vel_read = str(self.velEdit.text())
        lng_read = str(self.lngEdit.text())
        zero_read = str(self.zeroEdit.text())
        
        self.set_parms(accl_read, vel_read, lng_read, zero_read)
        self.back()

    def run_clicked(self):
        self.run()

    def back_clicked(self):
        self.back()

def main():
    
    app = QtGui.QApplication(sys.argv)
    win = GUI()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()





