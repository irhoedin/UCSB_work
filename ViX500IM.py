#Connex.py
__author__ = 'Hidenori Nakayama'
__version__ = '1.0'


import visa
import sys
from PyQt4 import QtGui, QtCore

address = '/dev/tty.usbserial-AI04WTCL'
baudrate = 9600
timeout = 1

class ViX500IM(object):
    def connect_module(self, adr=address, br=baudrate, timeout=timeout):
        import serial
        self.ser = serial.Serial(adr, br, timeout=timeout)
        self.move_right=True
        self.ser.write('1MI\r\n') #defines an incremental move. Starts from the current position.
        
    def set_parms(self, velocity, travel_len):
        
        #accelaration: fixed value
        self.ser.write('1A50.00\r\n') 
        
        #convert [mm] to [steps]. 50000 steps/3 mm
        travel_len_steps = str(int(float(travel_len)*(50000/3.)))
        self.ser.write('1D%s\r\n' %travel_len_steps)
        
        #convert [mm/s] to rev/s. 1rev/3 mm.
        vel_rev = str(round(float(velocity)/3., 3))
        self.ser.write('1V%s\r\n' %vel_rev)
        
    def run(self):
        if not self.move_right:
            self.ser.write('1H\r\n')
            
        self.ser.write('1G\r\n')
        self.move_right=True
        
    def back(self):
        if self.move_right:
            self.ser.write('1H\r\n')
            
        self.ser.write('1G\r\n')
        self.move_right=False
        
            
        



class GUI(QtGui.QWidget, ViX500IM):
    def __init__(self):
        super(GUI, self).__init__()
        self.initUI()

    
    def initUI(self):

        self.connect_btn = QtGui.QPushButton('CONNECT')
        self.connect_btn.setSizePolicy(QtGui.QSizePolicy.Preferred,
                    QtGui.QSizePolicy.Preferred)
        self.connect_btn.clicked.connect(self.connect_clicked)

        self.vel = QtGui.QLabel('VEL')
        self.lng = QtGui.QLabel('LNG')

        self.velEdit = QtGui.QLineEdit()
        self.lngEdit = QtGui.QLineEdit()

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


        self.grid.addWidget(self.vel, 1, 0)
        self.grid.addWidget(self.velEdit, 1, 1)
        
        self.grid.addWidget(self.lng, 1, 2)
        self.grid.addWidget(self.lngEdit, 1, 3)
        
        
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
        self.setWindowTitle('ViX500IM Interface by NORI')
        self.show()

    def connect_clicked(self):
        self.connect_module()

    def set_clicked(self):
        vel_read = str(self.velEdit.text())
        lng_read = str(self.lngEdit.text())
        
        self.set_parms(vel_read, lng_read)

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






