__version__ ="1p0"
"""
A module for controlling electronic instruments thourgh GPIB
"""

from import_all import *
import visa
import time
import datetime
from scipy import stats
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


    def conv_buffer2df(self, buffer_out, path_filename, auto_save=True):
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
        
        if auto_save:
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
        
        Return:
        path+filename: string
        filename: string
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


class Conductivity(GPIB_SetUp):
    """conductivity measurement using KE6220 and KE2400"""


    def __init__(self, gpib_add1, gpib_add2):
        """gpib_add1 for KE6220, gpib_add2 for KE2400"""
        
        rm = visa.ResourceManager(VISA_PATH)
        self.K6220 = rm.open_resource(gpib_add1)
        self.K2400 = rm.open_resource(gpib_add2)

        self.K6220_info = self.K6220.query('*IDN?')
        self.K2400_info = self.K2400.query('*IDN?')

        self.confirm_inst(self.K6220_info, '6220')
        self.confirm_inst(self.K2400_info, '2400')
        

    def measure(self, path, filename, gipb_add1='GPIB0::12::INSTR', gpib_add2='GPIB0::13::INSTR',
                           curr_start=-1e-3, curr_stop=1e-3, curr_step=1e-4,
                           sour_del=.01, nplc=1, graph=True, 
                           bias_curr=0., c_cmpl=1., v_cmpl=10.,
                           swp_rang='BEST', swe_coun=1):

        """Do conductivity measurment with KE6220 (current source) and KE2400 (source meter)
        
        DON'T change sour_del and nplc from the default value unless
        you really need it.
        Total step number should be not more than 21.
        Syncronizing two sweeps is tricky!
        
        Args:
        path: string, path of the directory to save file
        filename: string, filename
        curr_start: float, current start value [A]
        curr_stop: float, current stop value [A]
        curr_step: float, current sweep step [A]
        sour_del: float, source deley [s]
        nplc: float, nplc, if nplc=1, signal is integrated for 16.67 ms [-]
        graph: boolan, if True, a V-I plot appears
        bias_curr: float, bias applied by KE2400. SHOULD BE ZERO!
        c_cmpl: float, compliance current (applied for KE6220)
        v_cmpl: float, compliance voltage (applied for KE2400)
        swp_rang: string, refer 'SOUR:SWE:RANG' command for KE6220
        swe_count: integer, number of sweep. SHOULD BE 1!
        
        Rets:
        reg: float, registivity [Ohm]
        new_out_df: pd.DataFrame,
        columns=['Inpt_current', 'Bias', 'Current', 'Resistance', 'Time', 'Status']
        
        """

        path_filename, fn = self.confirm_unique_name(path, filename)
        
        step_num = (curr_stop - curr_start)/curr_step + 1
        sweep_time = self.cal_step_time(sour_del, nplc) * step_num
        print 'est. meas time : %d [s]' %sweep_time
        
        self.K2400.timeout = int(sweep_time * 1000 * 2)
        
        ## setup KE6220
        #basic settings
        inpt = self.K6220.write('*RST')

        inpt = self.K6220.write(':TRIG:SOUR TLIN') #event detector is trigger link
        inpt = self.K6220.write(':TRIG:ILIN 1') # triger input signal comes from line 1
        inpt = self.K6220.write(':TRIG:OLIN 2')# triger input signal send to line 2
        inpt = self.K6220.write(':TRIG:OUTP DEL') # after deley, triger output signal send to line 1
        inpt = self.K6220.write(':TRIG:DIR SOUR') #bypass triger at first 

        inpt = self.K6220.write('SOUR:CURR ' + str(bias_curr))
        inpt = self.K6220.write('SOUR:CURR:COMP ' + str(c_cmpl))

        #setting for sweep 
        inpt = self.K6220.write('SOUR:SWE:SPAC LIN')
        inpt = self.K6220.write('SOUR:CURR:STAR ' + str(curr_start))
        inpt = self.K6220.write('SOUR:CURR:STOP ' + str(curr_stop))
        inpt = self.K6220.write('SOUR:CURR:STEP ' + str(curr_step))
        inpt = self.K6220.write('SOUR:DEL ' + str(sour_del))
        inpt = self.K6220.write('SOUR:SWE:RANG ' + swp_rang)
        inpt = self.K6220.write('SOUR:SWE:COUN ' + str(swe_coun))
        inpt = self.K6220.write('SOUR:SWE:CAB OFF')
        inpt = self.K6220.write('SOUR:SWE:ARM')
        
        
        ## setup self.KE2400
        inpt = self.K2400.write('*RST') #reset
        
        inpt = self.K2400.write(':ARM:SOUR IMM') #set Arm
        inpt = self.K2400.write(':TRIG:SOUR TLIN') #Use "Triger Link" as trigger, new command (not checked)
        inpt = self.K2400.write(':TRIG:ILIN 2') #trigger input line 2 (input from K6220)
        inpt = self.K2400.write(':TRIG:OLIN 1') #trigger output line 1 (output to K6220)
        inpt = self.K2400.write(':TRIG:INP SENS') # trigger input to measure event detector (JPN man. 11-15)
        inpt = self.K2400.write(':TRIG:OUTP SENS') # trigger output after measure action
        inpt = self.K2400.write(':TRIG:COUN ' + str(step_num)) #set triger count = (start-end)/step + 1
        
        inpt = self.K2400.write(':SOUR:CLE:AUTO ON') #turn ON "auto out-put off"
        inpt = self.K2400.write(':SOUR:FUNC CURR')
        inpt = self.K2400.write(':SOUR:VOLT:MODE SWE') #set sweep mode
        inpt = self.K2400.write(':SOUR:CURR:LEV 0') #no current from the source meter
        inpt = self.K2400.write(':SOUR:DEL ' + str(sour_del)) #set source delay
        
        inpt = self.K2400.write(':SENS:FUNC \"VOLT\"') # sense Volt
        inpt = self.K2400.write(':SENS:VOLT:PROT ' + str(v_cmpl)) #set compliance
        inpt = self.K2400.write(':SENS:VOLT:NPLC ' + str(nplc)) #set compliance
        
        #execute sweep
        inpt = self.K6220.write('INIT:IMM')
        output = self.K2400.query(':READ?')    

        inpt = self.K6220.write('OUTP OFF')
        
        out_df = self.conv_buffer2df(output, path_filename, auto_save=False)
        input_current_df = pd.DataFrame(np.linspace(curr_start, curr_stop, step_num), columns=['Inpt_current'])
        new_out_df = pd.concat([input_current_df, out_df],axis=1)
        new_out_df.to_csv(path_filename + '.csv')
        
        #calculate resistance
        x = np.array(new_out_df['Inpt_current'])
        y = np.array(new_out_df['Voltage'])
        try:
            reg, b = np.polyfit(x, y, 1)
            print 'R = %.2e [Ohm]' %reg

        except:
            print 'regression unsuccessful'
        
        if graph:
            f, ax = plt.subplots()
            ax.plot(x, y, 'o')
            ax.set_xlabel('Current [A]')
            ax.set_ylabel('Voltage [V]')
                           
        return reg, new_out_df

class SeebeckFast(GPIB_SetUp):
    KE2400ADRS = 'GPIB0::13::INSTR' #Source Meter
    E3644AADRS = 'GPIB0::7::INSTR' #DC power supply
    F1529ADRS = 'GPIB0::22::INSTR' #Thermometer readout

    def __init__(self, sourcemeter=KE2400ADRS, power_spply=E3644AADRS, thermometer=F1529ADRS):
        """initialize the instant.

        sourcemeter: string, GPIB address for source meter. Keithley 2400.
        power_spply: string, GPIB address for DC power supply. Agilent E3644A.
        thermocouple: string, GPIB address for thermometer readout. Hart Scientific FLUKE 1529 CHUB E-4.
        """

        rm = visa.ResourceManager(VISA_PATH)
        self.K2400 =rm.open_resource(sourcemeter)
        self.E3644 =rm.open_resource(power_spply)
        self.F1529 =rm.open_resource(thermometer)

        self.K2400_info = self.K2400.query('*IDN?')
        self.E3644_info = self.E3644.query('*IDN?')
        self.F1529_info = self.F1529.query('*IDN?')

        self.confirm_inst(self.K2400_info, '2400')
        self.confirm_inst(self.E3644_info, '3644')
        self.confirm_inst(self.F1529_info, '1529')

        #Setup thermometer
        inpt = self.F1529.write('UNIT:TEMP C')

        inpt = self.F1529.write('ROUT:OPEN 1')
        inpt = self.F1529.write('ROUT:OPEN 2')
        inpt = self.F1529.write('ROUT:OPEN 3')
        inpt = self.F1529.write('ROUT:OPEN 4')
        
        inpt = self.F1529.write('ROUT:CLOS 1')
        inpt = self.F1529.write('ROUT:CLOS 2')

        print 'wait enough for themometer setup'

    def measure(self, path, filename, cycle_time=1., settling_time=75., max_voltage=1.):
        """measure Seebeck coefficient

        Args:
        cycle_time: float, period of voltage and temperature readout [s]
        settling_time: float, time to settle the temperature difference [s]
        max_voltage: float, maximum voltage to apply to percie from DC source. [V]

        Rets:
        alpha: float, Seebeck coefficient [V/K]
        dT_dV: panda.DataFrame, delta T vs delta V
        raw_data: panda.DataFrame, column=['time', 'voltage', 'delT', 'T1', 'T2']
        """

        sns.set(style="ticks")

        path_filename, fn = self.confirm_unique_name(path, filename)


        #Setup Keithley
        inpt = self.K2400.write('*RST')
        inpt = self.K2400.write(':SOUR:FUNC CURR')
        inpt = self.K2400.write(':SOUR:CURR:MODE FIXED')
        inpt = self.K2400.write(':SOUR:VOLT:LEV 0')
        inpt = self.K2400.write(':SENS:FUNC "VOLT"')
        inpt = self.K2400.write(':SENS:VOLT:PROT 1') #voltage compliance 1 V
        inpt = self.K2400.write(':SENS:VOLT:RANG 0.01') #Rrange 10 mV
        inpt = self.K2400.write(':FORM:ELEM VOLT') #output format, only voltage
        inpt = self.K2400.write(':OUTP ON')
        

        #Setup DC Power Supply
        inpt = self.E3644.write('*RST')
        inpt = self.E3644.write('CURR 3') #Current 3 A, fixed
        
        volt_prot = self.E3644.query('VOLT:PROT:STAT?') #over voltage protection? 1 = on, 0 = off
        if not volt_prot:
            inpt = self.E3644.write('VOLT:PROT:STAT ON')

        inpt = self.E3644.write('VOLT:PROT 22')
        inpt = self.E3644.write('VOLT 0')
        inpt = self.E3644.write('OUTP ON')

        
        #Start scan
        time_list = []
        delT_delV_list = []

        num_of_measure = settling_time/cycle_time

        fig, ax = plt.subplots(1, 2, figsize=(8,4))
        ax01 = ax[0].twinx()
        plt.tight_layout()
        plt.ion()

        fig.show()
        fig.canvas.draw()

        start_time = datetime.datetime.now()

        for i, voltage in enumerate(np.linspace(-max_voltage, max_voltage, 5)):
            self.E3644.write('VOLT '+ str(abs(voltage)))
        
            if voltage == 0:
                sys = raw_input('Switch the polarity of DC power and hit Enter!')

            for n in range(int(num_of_measure)):
                now = datetime.datetime.now()
                elasped = (now - start_time).total_seconds()
                voltage = self.K2400.query(':READ?')
                t1 = self.F1529.query('FETC? 1')
                t2 = self.F1529.query('FETC? 2')

                time_list.append([elasped, float(voltage), float(t1) - float (t2), float(t1), float(t2)])

                if n > num_of_measure - 5:
                    delT_delV_list.append([float(t1) - float(t2), float(voltage)])

                df = pd.DataFrame(time_list, columns=['time', 'voltage', 'delT', 'T1', 'T2'])
                df2 = pd.DataFrame(delT_delV_list, columns=['delT', 'delV'])

                ax[0].clear()
                ax[1].clear()
                ax01.clear()

                ax[0].plot(df['time'], df['voltage'], c='blue')
                ax[0].set_xlabel('time [s]')
                ax[0].set_ylabel('del V [V]')
                ax[0].yaxis.label.set_color('blue')
                ax01.plot(df['time'], df['delT'], c='black')
                ax01.set_ylabel('del T [K]')

                try:
                    ax[1].plot(df2['delT'], df2['delV'], 'o')

                    if i > 0:
                        x = np.array(df2['delT'])
                        y = np.array(df2['delV'])
                        
                        alpha, intercept, r_value, p_value, std_err = stats.linregress(x,y)
                        y_new = alpha * x + intercept
                        ax[1].plot(df2['delT'], df2['delV'], 'o')
                        ax[1].plot(x, y_new, '-', c='blue')
                        ax[1].set_xlabel('del T [K]')
                        ax[1].set_ylabel('del V [V]')
                        ax[1].plot(x, y_new, '-', c='blue')
                        ax[1].set_title('%0.2e [V/K]' %alpha) 

                except AttributeError:
                    ax[1].plot([0],[0])

                ax[1].set_xlabel('del T [K]')
                ax[1].set_ylabel('del V [V]')
                plt.tight_layout()
                fig.canvas.draw()


                time.sleep(1)

        
        inpt =self.E3644.write('OUTP OFF')
        inpt = self.K2400.write('OUTP OFF')
        inpt = self.K2400.write(':SYST:BEEP:STAT1')

        inpt = self.K2400.write(':SYST:BEEP 1780,0.2')
        time.sleep(0.2)
        inpt = self.K2400.write(':SYST:BEEP 1780,0.2')
        time.sleep(0.2)
        inpt = self.K2400.write(':SYST:BEEP 1780,0.2')

        df.to_csv(path_filename + '_tl.csv')
        df2.to_csv(path_filename + '_delTV.csv')

        print 'The Seebeck coefficient is %.2e [K/V]' %alpha


        return alpha, time_list, delT_delV_list






