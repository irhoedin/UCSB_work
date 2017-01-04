__version__ ="1p0"
"""
A module for controlling electronic instruments thourgh GPIB
"""

from import_all import *
import visa
import time
import datetime
import matplotlib.ticker as ptick

VISA_PATH = '/Library/Frameworks/Visa.framework/VISA'


class GPIB_SetUp(object):
    
    def __init__(self, gpib_addr):
    #Connect to GPIB. Get the instrument information
        
        rm = visa.ResourceManager(VISA_PATH)
        self.inst = rm.open_resource(gpib_addr)
        self.info = self.inst.query('*IDN?')
        print self.info


    def confirm_inst(self, idn_back, inst_name_key):
        """Check the instrument is correct.

        If not, raise AddressError

        """
        idn_back_enc = idn_back.encode('utf-8')

        if inst_name_key in idn_back_enc:
            print '%s confirmed' %inst_name_key
            return 0

        else:
            msg =  'This is not %s.' %inst_name_key
            raise AddressError(msg)


    def conv_buffer2df(self, buffer_out, path_filename):
        """Convert raw buffer data to DataFrame and save as a csv file.
        
        Args:
        buffer_out: string, buffer data (unicode)
        path_filename: string, full address of the file

        Ret:
        out_df: pd.DataFrame columns=['Voltage', 'Current', 'Registance', 'Time', 'Status']
        """

        out = buffer_out.encode('utf-8') #convert unicode to byte literal
        out_list = out.strip().split(',') #remove newline and split to list
        out_num = map(float, out_list) # DON'T FORGET to convert string to float (lost 30 min!)
        out_len = len(out_num)
        out_np = np.array(out_num)
        out_np2 = out_np.reshape(out_len/5, 5) #defaoult output records five values each readout. see blow.
        out_df = pd.DataFrame(out_np2,
                              columns=['Voltage', 'Current', 'Registance', 'Time', 'Status']) #default output
        
        out_df.to_csv(path_filename + '.csv')

        return out_df


    def plot_buffer_df(self, out_df, title):
        """recieve DataFrame and plot voltage vs current """
        
        f, ax = plt.subplots(figsize=(6,6))
        ax.plot(out_df['Voltage'], out_df['Current'], 'o-')
        ax.set_xlabel('Voltage [V]')
        ax.set_ylabel('Current [A]')
        ax.set_title(title)
    

    def confirm_unique_name(self, path, filename):
        """Confirm the filename is unique or not.
        
        Return path+filename
        """

        import glob
        while True:
            path_name = path + '/' + filename
            name_list = glob.glob(path_name + '*')
            if len(name_list):
                filename = raw_input('Hey! \"%s\" alrady exists in this directory!!\nEnter a new name: ' %filename)
            
            else:
                print '\"%s\" is an unique filename!' %filename
                return path + '/' + filename, filename

    def read_register(self, output, digit):
        out_enc = output.encode('utf-8')
        out_binary = str(format(int(out_enc), 'b'))
        out_string = out_binary.zfill(digit)
        return out_string


    def cal_step_time(self, sdel, nplc, tdel=0, freq=60.):
        """calculate measurment time in each step.
        
        See Appendex A of the KE2400 manual
        
        Args:
        sdel: float, source deleay [s]
        nplc: float, nplc [cycle]
        tdel: float, trigger dekay [s]
        freq: float, frequency of the power source [Hz]

        Ret:
        total time: float, total time for measureing each step
        """
        TRIG_WAIT = 255e-6 #[s]
        SOURCE_SET = 50e-6 #[s]
        FARMWAER_OVERHEAD = 1.8e-3 #[s] for V source measurement
        
        source_on = SOURCE_SET + sdel + 3 * (nplc * float(1/freq) + 185e-6) + FARMWAER_OVERHEAD
        
        total_time = TRIG_WAIT + tdel + source_on
        
        return total_time

          
class KE2400(GPIB_SetUp):
    """controls Keithley source meter 2400"""

    def __init__(self, gpib_addr):
        GPIB_SetUp.__init__(self, gpib_addr)
        self.confirm_inst(self.info, "2400")


    def iv_sweep_core(self, v_start, v_end, v_step, sdel=0.05, cmpl=0.1, nplc=0.1):
        """do I-V sweep on Keitheley 2400 source meter.
        
        Args:
        v_start: float, start voltage [V]
        v_end: float, end voltage [V]
        v_step: float, voltage steps [V]
        sdel: float, source delay [s]
        cmpl: float, compliance current [A]
        nplc: integer, Number of Power Line cycles (integration time)
            nplc = 1 takes 16.67 (1/60) msec in theory
        
        Ret:
        output: pd.DataFrame with the columns of [voltage, , , , ]
        """
        
        ADD_TIME = 0.05 #emperical additional time for nplc
        TIME_LAG = 3 #time lag between INIT and starting the while loop

        trg_cnt = round(abs(v_start - v_end)/v_step + 1)
        s_trg_cnt = str(trg_cnt)
        
        sweep_time = self.cal_step_time(sdel, nplc) * trg_cnt
        print 'est. scan time = %d [s]' %sweep_time

        self.inst.timeout = int(sweep_time * 1000 * 2)
        
        inpt = self.inst.write('*RST') #reset
        inpt = self.inst.write(':SOUR:CLE:AUTO ON') #set auto out-put off
        inpt = self.inst.write(':SENS:FUNC \'CURR:DC\'') # sense DC current
        inpt = self.inst.write(':SENS:CURR:DC:NPLCycles ' + str(nplc))
        inpt = self.inst.write(':SENS:CURR:PROT ' + str(cmpl)) #set compliance
        inpt = self.inst.write(':SOUR:VOLT:START ' + str(v_start)) #set votage start
        inpt = self.inst.write(':SOUR:VOLT:STOP ' + str(v_end)) #set voltage end
        inpt = self.inst.write(':SOUR:VOLT:STEP ' + str(v_step)) #set voltage step
        inpt = self.inst.write(':SOUR:VOLT:MODE SWE') #set sweep mode
        inpt = self.inst.write(':TRIG:COUN ' + s_trg_cnt) #set triger count = (start-end)/step + 1
        inpt = self.inst.write(':SOUR:DEL ' + str(sdel)) #set source delay

        buffer_out = self.inst.query(':READ?') #start sweep and wait for return
        
        return buffer_out

    
    def iv_sweep(self, path, filename, v_start, v_end, v_step, sdel=0.05, cmpl=0.1, nplc=0.1, graph=True):
        """do I-V sweep, record data, show graph


        Args:
        path: string, full path of the directory
        filename: string, filename without extention
        v_start: float, start voltage [V]
        v_end: float, end voltage [V]
        v_step: float, voltage steps [V]
        sdel: float, source delay [s]
        cmpl: float, compliance current [A]
        nplc: integer, Number of Power Line cycles (integration time)
            nplc = 1 takes 16.67 (1/60) msec in theory
        graph: boolan, if true, graph will apprar
        
        Ret:
        out_df: pd.DataFrame on fetched data from buffer
        """

        path_file, filename = self.confirm_unique_name(path, filename)
    
        buffer_out = self.iv_sweep_core(v_start, v_end, v_step)
        out_df = self.conv_buffer2df(buffer_out, path_file)

        if graph:
            self.plot_buffer_df(out_df, filename)

        return out_df


    def realtime_current(self, path, filename, v_lev, freq, duration, v_rang=20, cmpl=10e-3, c_range=10e-3):
        """Show realtime current under constant voltage on iphython notebook

        DON'T forget the following magics for the real time show!!

        %matplotlib inline
        %load_ext autoreload
        %autoreload 2
        %matplotlib nbagg


        Args:
        path: string, full path of the directory
        filename: string, filename without extention
        freq: float, data reading freaquency [Hz]
        duration: float, measurment duration time [s]
        v_lev: float, voltage [V]
        v_range: float, voltage range to show in the display [V]
        cmpl: float, comliance voltage [V]
        c_range: float, current range to show in the display [A]

        Ret:
        out_df: pd.DataFrame on current-time data
        """

        path_file, filename = self.confirm_unique_name(path, filename)
        
        intv = 1 / freq #[s]
        cycle = int(duration/intv)

        fig, ax = plt.subplots(figsize=(6,6))
        plt.ion()

        fig.subplots_adjust(left=0.2, bottom=0.15, right=0.95, top=0.95)

        fig.show()
        fig.canvas.draw()

        time_list=[]
        current_list=[]

        inpt = self.inst.write('*RST')
        inpt = self.inst.write(':SOUR:FUNC VOLT')
        inpt = self.inst.write(':SOUR:VOLT:MODE FIXED')
        inpt = self.inst.write(':SOUR:VOLT:RANG ' + str(v_rang))
        inpt = self.inst.write(':SOUR:VOLT:LEV ' + str(v_lev))
        inpt = self.inst.write(':SENS:CURR:PROT ' + str(cmpl)) 
        inpt = self.inst.write(':SENS:FUNC "CURR"')
        inpt = self.inst.write(':SENS:CURR:RANG ' + str(c_range))
        inpt = self.inst.write(':FORM:ELEM CURR')
        inpt = self.inst.write(':OUTP ON')
        now0 = datetime.datetime.now()

        for cycle in range(cycle):
            ax.clear()
            now = datetime.datetime.now()
            elasped = (now - now0).total_seconds()
            output = self.inst.query(':READ?')
            
            time_list.append(elasped)
            current_list.append(float(output))
            
            ax.plot(time_list, current_list, 'o')
            ax.set_xlabel('time')
            ax.set_ylabel('current [A]')
            ax.set_title(filename)
            ax.yaxis.set_major_formatter(ptick.ScalarFormatter(useMathText=True)) 
            ax.yaxis.offsetText.set_fontsize(10)
            ax.ticklabel_format(style='sci',axis='y',scilimits=(0,0))
            fig.canvas.draw()
            
            time.sleep(intv)

        inpt = self.inst.write(':OUTP OFF')

        out_df = pd.DataFrame([time_list, current_list], index=['time', 'current']).T
        out_df.to_csv(path_file + '.csv')

        return out_df


    def v_sweep(self, path, filename, curr_lev, trg_cnt, sdel, cmpl=21, nplc=0.1, graph=True):
        """sweep V with constant current
        
        Args:
        path: string, path of the directory
        filename: string, filename without extention
        curr_lev: float, current level [A]
        trg_cnt: integer, the number of the steps
        sdel: source delay time [s]
        cmpl: float(=21), compliance current [A] 
        nplc: float(=0.1), Number of Power Line cycles (integration time)
            nplc = 1 takes 16.67 (1/60) msec in theory
        
        Ret:
        output: pd.DataFrame with the columns of [voltage, , , , ]
        """
    
        ADD_time = 0.05 #emperical additional time for nplc
        TIME_LAG = 3 #time lag between INIT and starting the while loop

        sweep_time = (sdel + nplc * (0.01667 + ADD_time)) * trg_cnt
        
        path_filename, filename = self.confirm_unique_name(path, filename)
        
        print 'est. scan time = %d [s]' %sweep_time
        
        inpt = self.inst.write('*RST') #reset
        inpt = self.inst.write(':SOUR:CLE:AUTO ON') #set auto out-put off
        inpt = self.inst.write(':SOUR:FUNC CURR')
        inpt = self.inst.write(':SENS:FUNC \"VOLT\"') # sense Volt
        inpt = self.inst.write(':SOUR:CURR:START 0') #necessary?? set votage start
        inpt = self.inst.write(':SOUR:CURR:STOP 0') #necessary?? set voltage end
        inpt = self.inst.write(':SOUR:CURR:STEP 0') #necessary?? set voltage step
        inpt = self.inst.write(':SOUR:VOLT:MODE SWE') #set sweep mode
     
        inpt = self.inst.write(':SOUR:CURR:LEV ' + str(curr_lev))
        inpt = self.inst.write(':SOUR:DEL ' + str(sdel)) #set source delay
        inpt = self.inst.write(':SENS:VOLT:PROT ' + str(cmpl)) #set compliance
        inpt = self.inst.write(':SENS:VOLT:NPLC ' + str(nplc)) #set compliance
        inpt = self.inst.write(':TRIG:COUN ' + str(trg_cnt)) #set triger count = (start-end)/step + 1
        
        
        inpt = self.inst.write(':INIT') #start sweep
        
        time.sleep(TIME_LAG)

        while True:
            time.sleep(1)
            opr = self.inst.query(':STAT:OPER:EVEN?')
            reg = self.read_register(opr, 16)
            # print i, reg
            if reg[-11]=='1': #if "idle"(B11) is on 
                print 'scan completed'
                break
        
        buffer_out = self.inst.query(':FETC?')
        
        out_df = self.conv_buffer2df(buffer_out, path_filename)

        if graph:
            self.plot_buffer_df(out_df, filename)

        return out_df
