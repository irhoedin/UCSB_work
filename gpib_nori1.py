__version__ = "1p0"
"""
A module for controlling electronic instruments thourgh GPIB
"""

from import_all import *
import visa
import time
import datetime
from scipy import stats
import matplotlib.ticker as ptick
import signal
import sys
import platform

VISA_PATH = '/Library/Frameworks/Visa.framework/VISA'


def calc_rs(r_list, wl_list=[1. / 0.2, 1. / 0.5, 1. / 0.8], thickness=1):
    """calculte sheet resistance
    
    Args:
    r_list: list of float, list of resitance in Ohm.
    wl_list: list of float, list of W/L. Default is for TE mask at the C-lab
    thickness: float, thickness in [nm].
    If 1, conductivity calculation will not be done.
    
    Ret:
    rs: float, Sheet resistance [Ohm/sq]
    rc: float, contact resistance [Ohm]
    cond: float, conductivity [S/cm], only if thickness is not 1.
    """
    r = np.array(r_list)
    wl = np.array(wl_list)

    f, ax = plt.subplots(figsize=(4, 4))
    ax.plot(1 / wl, r, 'o')
    z = np.polyfit(1 / wl, r, 1)
    rs, rc = z[0], z[1]  # [Ohm/sq], [Ohm]

    lw = np.array([0, (1 / wl).max()])
    r_fit = lw * rs + rc

    ax.plot(lw, r_fit)

    if thickness == 1:
        print 'Rs = %e [Ohm/sq], Rc = %e [Ohm]' % (rs, rc)
        return rs, rc

    else:
        cond = (1 / rs) / (thickness * 1e-7)  # [S/cm]
        print 'Rs = {:0.2e} [Ohm/sq], Rc = {:0.2e} [Ohm]\nRho = {:0.2e} [S/cm]'\
            .format(rs, rc, cond)
        return rs, rc, cond


class GPIB_SetUp(object):
    def __init__(self, *gpib_adrs):
        # Connect to GPIB. Get the instrument information

        if platform.system() == 'Darwin': #Mac OS with NI-MAX
            rm = visa.ResourceManager(VISA_PATH)

        else: #Here assume Windows
            rm = visa.ResourceManager()

        self.inst = []
        self.info = []
        for adr in gpib_adrs:
            inst = rm.open_resource(adr)
            info = inst.query('*IDN?')
            self.inst.append(inst)
            self.info.append(info)
            print info


    def confirm_inst(self, idn_back, inst_name_key):
        """Check the instrument is correct.

        If not, raise AddressError

        """
        idn_back_enc = idn_back.encode('utf-8')

        if inst_name_key in idn_back_enc:
            print '%s confirmed' % inst_name_key
            return 0

        else:
            msg = 'This is not %s.' % inst_name_key
            raise AddressError(msg)

    def conv_buffer2df(self, buffer_out, path_filename, auto_save=True):
        """Convert raw buffer data to DataFrame and save as a csv file.
        
        Args:
        buffer_out: string, buffer data (unicode)
        path_filename: string, full address of the file

        Ret:
        out_df: pd.DataFrame columns=[
        'Voltage', 'Current', 'Registance', 'Time', 'Status']
        """

        out = buffer_out.encode('utf-8')  # convert unicode to byte literal
        out_list = out.strip().split(',')  # remove newline and split to list
        # DON'T FORGET to convert string to float (lost 30 min!)
        out_num = map(float, out_list)
        out_len = len(out_num)
        out_np = np.array(out_num)
        # defaoult output records five values each readout. see blow.
        out_np2 = out_np.reshape(out_len / 5, 5)
        out_df = pd.DataFrame(out_np2,
                              columns=['Voltage', 'Current', 'Registance',
                                       'Time', 'Status'])  # default output

        if auto_save:
            out_df.to_csv(path_filename + '.csv')

        return out_df

    def plot_buffer_df(self, out_df, title):
        """recieve DataFrame and plot voltage vs current """

        f, ax = plt.subplots(figsize=(6, 6))
        ax.plot(out_df['Voltage'], out_df['Current'], 'o-')
        ax.set_xlabel('Voltage [V]')
        ax.set_ylabel('Current [A]')
        ax.set_title(title)
        return f, ax

    def confirm_unique_name(self, path, filename):
        """Confirm the filename is unique or not.
        
        Return:
        path+filename: string
        filename: string
        """

        import glob
        while True:
            if len(path) == 0:
                path_name = filename

            else:
                path_name = path + '/' + filename

            name_list = glob.glob(path_name + '*')
            if len(name_list):
                filename = raw_input(
                    'Hey! \"%s\" alrady exists in this directory!!' %filename \
                    + '\nEnter a new name: ')

            else:
                print '\"%s\" is an unique filename!' % filename
                return path_name, filename

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

        TRIG_WAIT = 255e-6  # [s]
        SOURCE_SET = 50e-6  # [s]
        FARMWAER_OVERHEAD = 1.8e-3  # [s] for V source measurement

        source_on = SOURCE_SET + sdel + 3*(nplc*float(1/freq) + 185e-6) \
                    + FARMWAER_OVERHEAD

        total_time = TRIG_WAIT + tdel + source_on

        return total_time


class KE2400(GPIB_SetUp):
    """controls Keithley source meter 2400"""
    smu_adr = "GPIB0::13::INSTR"

    def __init__(self, gpib_adr=smu_adr):
        GPIB_SetUp.__init__(self, gpib_adr)
        self.confirm_inst(self.info[0], "2400")

    def iv_sweep_core(self, v_start, v_end, v_step,
                      sdel=0.05, cmpl=0.1, nplc=0.1):
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

        ADD_TIME = 0.05  # emperical additional time for nplc
        TIME_LAG = 3  # time lag between INIT and starting the while loop

        trg_cnt = round(abs(v_start - v_end) / v_step + 1)
        s_trg_cnt = str(trg_cnt)

        sweep_time = self.cal_step_time(sdel, nplc) * trg_cnt
        print 'est. scan time = %d [s]' % sweep_time

        self.inst[0].timeout = int(sweep_time * 1000 * 2)

        inpt = self.inst[0].write('*RST')  # reset
        inpt = self.inst[0].write(':SOUR:CLE:AUTO ON')  # set auto out-put off
        inpt = self.inst[0].write(':SENS:FUNC \'CURR:DC\'')  # sense DC current
        inpt = self.inst[0].write(':SENS:CURR:DC:NPLC ' + str(nplc))
        inpt = self.inst[0].write(':SENS:CURR:PROT ' + str(cmpl))  # set compliance
        inpt = self.inst[0].write(':SOUR:VOLT:START ' + str(v_start))  # set votage start
        inpt = self.inst[0].write(':SOUR:VOLT:STOP ' + str(v_end))  # set voltage end
        inpt = self.inst[0].write(':SOUR:VOLT:STEP ' + str(v_step))  # set voltage step
        inpt = self.inst[0].write(':SOUR:VOLT:MODE SWE')  # set sweep mode
        inpt = self.inst[0].write(':TRIG:COUN ' + s_trg_cnt)  # set triger count = (start-end)/step + 1
        inpt = self.inst[0].write(':SOUR:DEL ' + str(sdel))  # set source delay

        buffer_out = self.inst[0].query(':READ?')  # start sweep and wait for return

        return buffer_out

    def iv_sweep(self, path, filename, v_start, v_end, v_step,
                 sdel=0.05, cmpl=0.1, nplc=0.1, graph=True, res=True):
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
        res: boolan, if true, registivity is calculated based on linear regression of 
            the I-V characteristic and shown. 
        
        Ret:
        out_df: pd.DataFrame on fetched data from buffer
        """

        path_file, filename = self.confirm_unique_name(path, filename)

        buffer_out = self.iv_sweep_core(v_start, v_end, v_step)
        out_df = self.conv_buffer2df(buffer_out, path_file)

        if graph:
            f, ax = self.plot_buffer_df(out_df, filename)

        if res:
            current = out_df['Current']
            voltage = out_df['Voltage']
            a, b = np.polyfit(voltage, current, 1)
            fit_current = a * voltage + b
            ax.plot(voltage, fit_current, '-')
            print 'The conductivity is {:0.2e} [S].' \
                  '\nSection is {:0.2e} [A]'.format(a, b)

        return out_df

    def realtime_current(self, path, filename, v_lev, freq, duration,
                         v_rang=20, cmpl=10e-3, c_range=10e-3):
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

        intv = 1 / freq  # [s]
        cycle = int(duration / intv)

        fig, ax = plt.subplots(figsize=(6, 6))
        plt.ion()

        fig.subplots_adjust(left=0.2, bottom=0.15, right=0.95, top=0.95)

        fig.show()
        fig.canvas.draw()

        time_list = []
        current_list = []

        inpt = self.inst[0].write('*RST')
        inpt = self.inst[0].write(':SOUR:FUNC VOLT')
        inpt = self.inst[0].write(':SOUR:VOLT:MODE FIXED')
        inpt = self.inst[0].write(':SOUR:VOLT:RANG ' + str(v_rang))
        inpt = self.inst[0].write(':SOUR:VOLT:LEV ' + str(v_lev))
        inpt = self.inst[0].write(':SENS:CURR:PROT ' + str(cmpl))
        inpt = self.inst[0].write(':SENS:FUNC "CURR"')
        inpt = self.inst[0].write(':SENS:CURR:RANG ' + str(c_range))
        inpt = self.inst[0].write(':FORM:ELEM CURR')
        inpt = self.inst[0].write(':OUTP ON')
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
            ax.ticklabel_format(style='sci', axis='y', scilimits=(0, 0))
            fig.canvas.draw()

            time.sleep(intv)

        inpt = self.inst.write(':OUTP OFF')

        out_df = pd.DataFrame([time_list, current_list],
                              index=['time', 'current']).T
        out_df.to_csv(path_file + '.csv')

        return out_df

    def v_sweep(self, path, filename, curr_lev, trg_cnt, sdel,
                cmpl=21, nplc=0.1, graph=True):
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

        ADD_time = 0.05  # emperical additional time for nplc
        TIME_LAG = 3  # time lag between INIT and starting the while loop

        sweep_time = (sdel + nplc * (0.01667 + ADD_time)) * trg_cnt

        path_filename, filename = self.confirm_unique_name(path, filename)

        print 'est. scan time = %d [s]' % sweep_time

        inpt = self.inst[0].write('*RST')  # reset
        inpt = self.inst[0].write(':SOUR:CLE:AUTO ON')  # set auto out-put off
        inpt = self.inst[0].write(':SOUR:FUNC CURR')
        inpt = self.inst[0].write(':SENS:FUNC \"VOLT\"')  # sense Volt
        inpt = self.inst[0].write(':SOUR:CURR:START 0')  # necessary?? set votage start
        inpt = self.inst[0].write(':SOUR:CURR:STOP 0')  # necessary?? set voltage end
        inpt = self.inst[0].write(':SOUR:CURR:STEP 0')  # necessary?? set voltage step
        inpt = self.inst[0].write(':SOUR:VOLT:MODE SWE')  # set sweep mode

        inpt = self.inst[0].write(':SOUR:CURR:LEV ' + str(curr_lev))
        inpt = self.inst[0].write(':SOUR:DEL ' + str(sdel))  # set source delay
        inpt = self.inst[0].write(':SENS:VOLT:PROT ' + str(cmpl))  # set compliance
        inpt = self.inst[0].write(':SENS:VOLT:NPLC ' + str(nplc))  # set compliance
        inpt = self.inst[0].write(':TRIG:COUN ' + str(trg_cnt))  # set triger count = (start-end)/step + 1

        inpt = self.inst[0].write(':INIT')  # start sweep

        time.sleep(TIME_LAG)

        while True:
            time.sleep(1)
            opr = self.inst.query(':STAT:OPER:EVEN?')
            reg = self.read_register(opr, 16)
            # print i, reg
            if reg[-11] == '1':  # if "idle"(B11) is on
                print 'scan completed'
                break

        buffer_out = self.inst.query(':FETC?')

        out_df = self.conv_buffer2df(buffer_out, path_filename)

        if graph:
            self.plot_buffer_df(out_df, filename)

        return out_df


class KE2400withLED(KE2400):
    """
    Measure IV characteristics with KE2400 and THORLABS DC2200 LED controller
    """

    def __init__(self, smu_adr='GPIB0::13::INSTR'):
        #Get the lengthy address of DC2200
        def find_DC2200_adr():
            rm = visa.ResourceManager()
            res_list = rm.list_resources()
            DC2200_found = False
            for res in res_list:
                if 'USB0' in res:
                    test_inst = rm.open_resource(res)
                    try:
                        out = test_inst.query('*IDN?')
                        if 'DC2200' in out:
                            DC2200_found = True
                            return res
                            break
                    except:
                        pass

            if not DC2200_found:
                try:
                    raise Exception("DC2200 not found")
                except Exception, e:
                    print e

        dc2200_adr = find_DC2200_adr()
        GPIB_SetUp.__init__(self, smu_adr, dc2200_adr)
        self.confirm_inst(self.info[0], '2400')
        self.confirm_inst(self.info[1], '2200')

    def handler(self, singal, frame):
        """Catch interrupt button on Jupyter"""
        self.inst[0].write('*RST')
        self.inst[1].write('*RST')
        print 'Interrupted by User'
        sys.exit(1)

    def measure_IV_LED(self, path, filename, v_start, v_end, v_step, light_list,
                   sdel=0.05, cmpl=0.1, nplc=0.1, graph=True, res=True):
        """
        Measure IV characteristics under LED light
        :param path: string, filepath
        :param filename: string, filename
        :param v_start: float, start voltage
        :param v_end: float, end voltage
        :param v_step: float, voltage step
        :param light_list: list of integer, LED light power in %
        :param sdel: float, delay time (=0.05)
        :param cmpl: float, compliance current (=0.1)
        :param nplc: float, nplc (=0.1)
        :param graph: boolan, if True, show graph (=True)
        :param res: boolan, if True show linear fitting for ohmic resistance
                (=True)
        :return: list of DataFrames
        """

        signal.signal(signal.SIGINT, self.handler)

        self.inst[1].write('*RST') #Constant brightness mode
        self.inst[1].write(':SOUR:MODE 2') #Constant brightness mode
        self.inst[1].write(':SOUR:CBR 0') #Birhgtness = 0
        self.inst[1].write(':OUTP:STATE 1') #Birhgtness = 0

        df_list=[]

        for light in light_list:
            self.inst[1].write(':SOUR:CBR ' + str(light))

            filename_light = filename + '_LED' + str(light).zfill(3)

            out_df = self.iv_sweep(
                path=path, filename=filename_light, v_start=v_start,
                v_end=v_end, v_step=v_step, sdel=sdel, cmpl=cmpl, nplc=nplc,
                graph=graph, res=res)

            df_list.append(out_df)


        self.inst[1].write(':OUTP:STATE 0') #turn off the output

        return df_list




class Conductivity(GPIB_SetUp):
    """conductivity measurement using KE6220 and KE2400
    
    Args:
    gpib_add1: string, GPIB address for KE6220 current source
    gpib_add2: string, GPIB address for KE2400 SMU
    """

    KE6220_adrs = 'GPIB0::12::INSTR'
    KE2400_adrs = 'GPIB0::13::INSTR'

    def __init__(self, gpib1=KE6220_adrs, gpib2=KE2400_adrs):
        """gpib_add1 for KE6220, gpib_add2 for KE2400"""

        GPIB_SetUp.__init__(self, gpib1, gpib2)
        self.confirm_inst(self.info[0], "6220")
        self.confirm_inst(self.info[1], "2400")

    def measure(self, path, filename, curr_start=-1e-3, curr_stop=1e-3,
                curr_step=1e-4, sour_del=.01, nplc=1, graph=True, bias_curr=0.,
                c_cmpl=100., v_cmpl=50., swp_rang='BEST', swe_coun=1):

        """Do conductivity measurment with KE6220 (current source) and
        KE2400 (source meter). Trigger link is required.
        
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
        c_cmpl: float, compliance current [V] (applied for KE6220)
        v_cmpl: float, compliance voltage [V] (applied for KE2400)
        swp_rang: string, refer 'SOUR:SWE:RANG' command for KE6220
        swe_count: integer, number of sweep. SHOULD BE 1!
        
        Rets:
        reg: float, registivity [Ohm]
        new_out_df: pd.DataFrame,
        columns=['Inpt_current', 'Bias', 'Current', 'Resistance', 'Time', 'Status']
        
        """

        path_filename, fn = self.confirm_unique_name(path, filename)

        step_num = (curr_stop - curr_start) / curr_step + 1
        sweep_time = self.cal_step_time(sour_del, nplc) * step_num
        print 'est. meas time : %d [s]' % sweep_time

        self.inst[1].timeout = int(sweep_time * 1000 * 2)

        ## setup KE6220
        # basic settings
        inpt = self.inst[0].write('*RST')

        inpt = self.inst[0].write(':TRIG:SOUR TLIN')  # event detector is trigger link
        inpt = self.inst[0].write(':TRIG:ILIN 1')  # triger input signal comes from line 1
        inpt = self.inst[0].write(':TRIG:OLIN 2')  # triger input signal send to line 2
        inpt = self.inst[0].write(':TRIG:OUTP DEL')  # after deley, triger output signal send to line 1
        inpt = self.inst[0].write(':TRIG:DIR SOUR')  # bypass triger at first

        inpt = self.inst[0].write('SOUR:CURR ' + str(bias_curr))
        inpt = self.inst[0].write('SOUR:CURR:COMP ' + str(c_cmpl))
        inpt = self.inst[0].write('OUTP:ISH OLOW')  # triaxial inner shield is output low
        inpt = self.inst[0].write('OUTP:LTE ON')  # Output low is internally connected to Earth Ground

        # setting for sweep
        inpt = self.inst[0].write('SOUR:SWE:SPAC LIN')
        inpt = self.inst[0].write('SOUR:CURR:STAR ' + str(curr_start))
        inpt = self.inst[0].write('SOUR:CURR:STOP ' + str(curr_stop))
        inpt = self.inst[0].write('SOUR:CURR:STEP ' + str(curr_step))
        inpt = self.inst[0].write('SOUR:DEL ' + str(sour_del))
        inpt = self.inst[0].write('SOUR:SWE:RANG ' + swp_rang)
        inpt = self.inst[0].write('SOUR:SWE:COUN ' + str(swe_coun))
        inpt = self.inst[0].write('SOUR:SWE:CAB OFF')
        inpt = self.inst[0].write('SOUR:SWE:ARM')

        ## setup self.KE2400
        inpt = self.inst[1].write('*RST')  # reset

        inpt = self.inst[1].write(':ARM:SOUR IMM')  # set Arm
        inpt = self.inst[1].write(':TRIG:SOUR TLIN')  # Use "Triger Link" as trigger, new command (not checked)
        inpt = self.inst[1].write(':TRIG:ILIN 2')  # trigger input line 2 (input from inst[0])
        inpt = self.inst[1].write(':TRIG:OLIN 1')  # trigger output line 1 (output to inst[0])
        inpt = self.inst[1].write(':TRIG:INP SENS')  # trigger input to measure event detector (JPN man. 11-15)
        inpt = self.inst[1].write(':TRIG:OUTP SENS')  # trigger output after measure action
        inpt = self.inst[1].write(':TRIG:COUN ' + str(step_num))  # set triger count = (start-end)/step + 1

        inpt = self.inst[1].write(':SOUR:CLE:AUTO ON')  # turn ON "auto out-put off"
        inpt = self.inst[1].write(':SOUR:FUNC CURR')
        inpt = self.inst[1].write(':SOUR:VOLT:MODE SWE')  # set sweep mode
        inpt = self.inst[1].write(':SOUR:CURR:LEV 0')  # no current from the source meter
        inpt = self.inst[1].write(':SOUR:DEL ' + str(sour_del))  # set source delay

        inpt = self.inst[1].write(':SENS:FUNC \"VOLT\"')  # sense Volt
        inpt = self.inst[1].write(':SENS:VOLT:PROT ' + str(v_cmpl))  # set compliance
        inpt = self.inst[1].write(':SENS:VOLT:NPLC ' + str(nplc))  # set compliance

        # execute sweep
        inpt = self.inst[0].write('INIT:IMM')
        output = self.inst[1].query(':READ?')

        inpt = self.inst[0].write('OUTP OFF')

        out_df = self.conv_buffer2df(output, path_filename, auto_save=False)
        input_current_df = pd.DataFrame(np.linspace(curr_start, curr_stop, step_num), columns=['Inpt_current'])
        new_out_df = pd.concat([input_current_df, out_df], axis=1)
        new_out_df.to_csv(path_filename + '.csv')

        # calculate resistance
        x = np.array(new_out_df['Inpt_current'])
        y = np.array(new_out_df['Voltage'])
        try:
            reg, b = np.polyfit(x, y, 1)
            print 'R = %.2e [Ohm]' % reg

        except:
            print 'regression unsuccessful'

        if graph:
            f, ax = plt.subplots()
            ax.plot(x, y, 'o')
            ax.set_xlabel('Current [A]')
            ax.set_ylabel('Voltage [V]')

        return reg, new_out_df


class SeebeckFast(GPIB_SetUp):
    KE2400ADRS = 'GPIB0::13::INSTR'  # Source Meter
    E3644AADRS = 'GPIB0::7::INSTR'  # DC power supply
    F1529ADRS = 'GPIB0::22::INSTR'  # Thermometer readout

    def __init__(self, sourcemeter=KE2400ADRS, power_spply=E3644AADRS, thermometer=F1529ADRS):
        """initialize the instant.

        sourcemeter: string, GPIB address for source meter. Keithley 2400.
        power_spply: string, GPIB address for DC power supply. Agilent E3644A.
        thermocouple: string, GPIB address for thermometer readout. Hart Scientific FLUKE 1529 CHUB E-4.
        """

        rm = visa.ResourceManager(VISA_PATH)
        self.K2400 = rm.open_resource(sourcemeter)
        self.E3644 = rm.open_resource(power_spply)
        self.F1529 = rm.open_resource(thermometer)

        self.K2400_info = self.K2400.query('*IDN?')
        self.E3644_info = self.E3644.query('*IDN?')
        self.F1529_info = self.F1529.query('*IDN?')

        self.confirm_inst(self.K2400_info, '2400')
        self.confirm_inst(self.E3644_info, '3644')
        self.confirm_inst(self.F1529_info, '1529')

        # Setup thermometer
        inpt = self.F1529.write('UNIT:TEMP C')

        inpt = self.F1529.write('ROUT:OPEN 1')
        inpt = self.F1529.write('ROUT:OPEN 2')
        inpt = self.F1529.write('ROUT:OPEN 3')
        inpt = self.F1529.write('ROUT:OPEN 4')

        inpt = self.F1529.write('ROUT:CLOS 1')
        inpt = self.F1529.write('ROUT:CLOS 2')

        print 'wait enough for themometer setup'

    def measure(self, path, filename, cycle_time=1.,
                settling_time=75., max_voltage=1.):
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

        # Setup Keithley
        inpt = self.K2400.write('*RST')
        inpt = self.K2400.write(':SYST:BEEP:STAT1')
        inpt = self.K2400.write(':SOUR:FUNC CURR')
        inpt = self.K2400.write(':SOUR:CURR:MODE FIXED')
        inpt = self.K2400.write(':SOUR:VOLT:LEV 0')
        inpt = self.K2400.write(':SENS:FUNC "VOLT"')
        inpt = self.K2400.write(':SENS:VOLT:PROT 1')  # voltage compliance 1 V
        inpt = self.K2400.write(':SENS:VOLT:RANG 0.01')  # Rrange 10 mV
        inpt = self.K2400.write(':FORM:ELEM VOLT')  # output format, only voltage
        inpt = self.K2400.write(':OUTP ON')

        # Setup DC Power Supply
        inpt = self.E3644.write('*RST')
        inpt = self.E3644.write('CURR 3')  # Current 3 A, fixed

        volt_prot = self.E3644.query('VOLT:PROT:STAT?')  # over voltage protection? 1 = on, 0 = off
        if not volt_prot:
            inpt = self.E3644.write('VOLT:PROT:STAT ON')

        inpt = self.E3644.write('VOLT:PROT 22')
        inpt = self.E3644.write('VOLT 0')
        inpt = self.E3644.write('OUTP ON')

        # Start scan
        time_list = []
        delT_delV_list = []

        num_of_measure = settling_time / cycle_time

        fig, ax = plt.subplots(1, 2, figsize=(8, 4))
        ax01 = ax[0].twinx()
        plt.tight_layout()
        plt.ion()

        fig.show()
        fig.canvas.draw()

        start_time = datetime.datetime.now()

        for i, voltage in enumerate(np.linspace(-max_voltage, max_voltage, 5)):
            self.E3644.write('VOLT ' + str(abs(voltage)))

            if voltage == 0:
                inpt = self.K2400.write(':SYST:BEEP 1780,1')
                time.sleep(1)
                sys = raw_input('Switch the polarity of DC power and hit Enter!')

            for n in range(int(num_of_measure)):
                now = datetime.datetime.now()
                elasped = (now - start_time).total_seconds()
                voltage = self.K2400.query(':READ?')
                t1 = self.F1529.query('FETC? 1')
                t2 = self.F1529.query('FETC? 2')

                time_list.append([elasped, float(voltage),
                                  float(t1)-float(t2), float(t1), float(t2)])

                if n > num_of_measure - 5:
                    delT_delV_list.append([float(t1)-float(t2),
                                           float(voltage)])

                df = pd.DataFrame(time_list,
                                  columns=[
                                      'time', 'voltage', 'delT', 'T1', 'T2'])
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

                        alpha, intercept, r_value, p_value, std_err \
                        = stats.linregress(x, y)
                        y_new = alpha*x + intercept
                        seebeck = -alpha  # S = -delV/delT in definition

                        ax[1].plot(df2['delT'], df2['delV'], 'o')
                        ax[1].plot(x, y_new, '-', c='blue')
                        ax[1].set_xlabel('del T [K]')
                        ax[1].set_ylabel('del V [V]')
                        ax[1].plot(x, y_new, '-', c='blue')
                        ax[1].set_title('%0.2e [V/K]' % seebeck)

                except AttributeError:
                    ax[1].plot([0], [0])

                ax[1].set_xlabel('del T [K]')
                ax[1].set_ylabel('del V [V]')
                plt.tight_layout()
                fig.canvas.draw()

                time.sleep(1)

        inpt = self.E3644.write('OUTP OFF')
        inpt = self.K2400.write('OUTP OFF')

        inpt = self.K2400.write(':SYST:BEEP 1780,0.2')
        time.sleep(0.2)
        inpt = self.K2400.write(':SYST:BEEP 1780,0.2')
        time.sleep(0.2)
        inpt = self.K2400.write(':SYST:BEEP 1780,0.2')

        df.to_csv(path_filename + '_tl.csv')
        df2.to_csv(path_filename + '_delTV.csv')

        print 'The Seebeck coefficient is %.2e [K/V]' % seebeck

        return seebeck, time_list, delT_delV_list


class TFTPico(GPIB_SetUp):
    """TFT measurement using a source measure unit and a picoammeter.
    
    SMU: K2400 for source-gate
    Picoammeter: K6487 for source-drain
    """

    smuadr = 'GPIB0::13::INSTR' #gate bias
    picoadr= 'GPIB0::11::INSTR'  #source-drain

    def __init__(self, gpib1=smuadr, gpib2=picoadr):
        GPIB_SetUp.__init__(self, gpib1, gpib2)
        self.confirm_inst(self.info[0], '2400')
        self.confirm_inst(self.info[1], '6487')

    def handler(self, singal, frame):
        """Catch interrupt button on Jupyter"""
        self.inst[0].write('*RST')
        self.inst[1].write('*RST')
        print 'Interrupted'
        sys.exit(1)

    def meas_output(self, path, filename, v_start=0., v_end=100., v_step=5.,
                    v_g_list=np.linspace(0., 100., 6.),
                    reverse=True, cmpl=0.1, nplc=6,
                    waiting_time=0.01):

        """ measure output characteristic
        
        Args:
        path: string, path of directory
        filename: string, filename
        v_start: float, V_SD start voltage [V]
        v_end: float, V_SD end voltage [V]
        v_step: float, V_SDvoltage increment [V]
        v_g_list: list of float, V_G list [V]
        sdel: float, source deley [s], def=0.05
        cmpl: float, compliance current [A], def=0.1
        nplc: float, number of power line cycles (integration time), def=6
        waiting_time:, float, waiting time after gate bias is set

        Ret: df: DataFrame,
        """

        #stop when interrupt
        signal.signal(signal.SIGINT, self.handler)

        path_file, filename = self.confirm_unique_name(path, filename)

        trg_cnt = round(abs(v_start - v_end) / v_step + 1)

        #set v_sd list_
        if reverse:
            v_sd_list = np.concatenate((
                np.linspace(v_start, v_end, trg_cnt),
                np.linspace(v_end, v_start, trg_cnt)),
                axis=0)

        else:
            v_sd_list = np.linspace(v_start, v_end, trg_cnt)

        # setup inst[0] (K2400)
        self.inst[0].timeout = int(2000)


        inpt = self.inst[0].write('*RST')
        inpt = self.inst[0].write(':SOUR:FUNC VOLT')
        inpt = self.inst[0].write(':SOUR:VOLT:MODE FIXED')
        inpt = self.inst[0].write(':SOUR:VOLT:RANG 120')
        inpt = self.inst[0].write(':SOUR:VOLT:LEV 0')
        inpt = self.inst[0].write(':SENS:CURR:PROT ' + str(cmpl))
        inpt = self.inst[0].write(':SENS:FUNC "CURR"')
        inpt = self.inst[0].write(':SENS:CURR:RANG 0.01')
        inpt = self.inst[0].write(':FORM:ELEM CURR')

        # setup inst[1] (K6487)
        inpt = self.inst[1].write('*RST')
        inpt = self.inst[1].write('SOUR:VOLT:RANG 100')
        inpt = self.inst[1].write('SOUR:VOLT:ILIM 0.001')
        inpt = self.inst[1].write('SENS:CURR:NPLC ' + str(nplc))
        inpt = self.inst[1].write('SOUR:VOLT 0')
        inpt = self.inst[1].write('SYST:ZCH OFF')

        # turn on the voltage
        inpt = self.inst[0].write(':OUTP ON')
        inpt = self.inst[1].write('SOUR:VOLT:STAT ON')

        #prep for figure
        fig, ax = plt.subplots(1, 2, figsize=(8,4))
        plt.ion()
        plt.tight_layout()
        fig.show()
        fig.canvas.draw()

        full_isd_list = []
        full_igd_list = []
        full_vsd_list = []
        for i, v_g in enumerate(v_g_list):
            inpt = self.inst[0].write(':SOUR:VOLT:LEV ' + str(v_g))
            full_isd_list.append([])
            full_igd_list.append([])
            full_vsd_list.append([])

            for v_sd in v_sd_list:
                inpt = self.inst[1].write('SOUR:VOLT ' + str(v_sd))
                time.sleep(waiting_time)
                outp2 = self.inst[1].query('READ?')
                i_sd = float(outp2.split(',')[0][:-1])

                outp1 = self.inst[0].query('READ?')
                i_vd = float(outp1)

                full_isd_list[i].append(i_sd)
                full_igd_list[i].append(i_vd)
                full_vsd_list[i].append(v_sd)

                #plot iv
                ax[0].clear()
                for volt, curr in zip(full_vsd_list, full_isd_list):
                    ax[0].plot(volt, curr)
                ax[0].set_xlabel('V_SD [V]')
                ax[0].set_ylabel('I_SD [A]')
                ax[0].set_title(filename + ' Vsd')
                ax[0].set_yscale('log')

                ax[1].clear()
                for volt, curr in zip(full_vsd_list, full_igd_list):
                    ax[1].plot(volt, curr)
                ax[1].set_xlabel('V_GD [V]')
                ax[1].set_ylabel('I_{SD} [A]')
                ax[1].set_title(filename + ' Vgd')
                ax[1].set_yscale('log')

                fig.canvas.draw()

                """print "Vg = {0:0.1f}, Vsd = {1:0.1f}, I_sd = {2:0.3e}".format(
                    v_g, v_sd, i_sd
                )"""

        inpt = self.inst[0].write('OUTP OFF')
        inpt = self.inst[1].write(':SOUR:VOLT:STAT OFF')

        df_isd = pd.DataFrame(full_isd_list).T
        df_isd.columns = ['Isd_Vg'+str(int(v_g)) for v_g in v_g_list]

        df_ig = pd.DataFrame(full_ig_list).T
        df_ig.columns = ['Ig_Vg'+str(int(v_g)) for v_g in v_g_list]

        df_all = pd.concat([df_isd, df_ig], axis=1)
        df_all['Vsd'] = full_vsd_lsit[0]

        df_all.to_csv(path_file + '.csv')

        return df

    def meas_transfer(self, path, filename, v_start=-10., v_end=100.,
                      v_step=5., v_sd_list=[20.,50.,80.],
                      reverse=True, cmpl=0.01, nplc=6, wait=0.01):

        """

        :param path: string, path of directory
        :param filename: string, filename
        :param v_start: float, V_G start=-10. [V]
        :param v_end: float, V_G end=100. [V]
        :param v_step: float, V_G step=5. [V]
        :param v_sd_list: list of float, V_SD list=[20., 50., 80.] [V]
        :param reverse: boolan, True
        :param cmpl: float, compliance=0.01 [A]
        :param nplc: float, nplc=6
        :param wait: waiting time after voltage is set = 0.01 [s]
        :return: df: DataFrame
        """

        #stop when interrupted
        signal.signal(signal.SIGINT, self.handler)

        path_file, filename = self.confirm_unique_name(path, filename)

        trg_cnt = round(abs(v_start - v_end) / v_step + 1)

        #set v_sd list_
        if reverse:
            v_g_list = np.concatenate((
                np.linspace(v_start, v_end, trg_cnt),
                np.linspace(v_end, v_start, trg_cnt)),
                axis=0)

        else:
            v_g_list = np.linspace(v_start, v_end, trg_cnt)

        # setup inst[0] (K2400)
        self.inst[0].timeout = int(2000)

        inpt = self.inst[0].write('*RST')
        inpt = self.inst[0].write(':SOUR:FUNC VOLT')
        inpt = self.inst[0].write(':SOUR:VOLT:MODE FIXED')
        inpt = self.inst[0].write(':SOUR:VOLT:RANG 120')
        inpt = self.inst[0].write(':SOUR:VOLT:LEV 0')
        inpt = self.inst[0].write(':SENS:CURR:PROT ' + str(cmpl))
        inpt = self.inst[0].write(':SENS:FUNC "CURR"')
        #inpt = self.inst[0].write(':SENS:CURR:RANG AUTO')
        inpt = self.inst[0].write(':FORM:ELEM CURR')

        # setup inst[1] (K6487)
        inpt = self.inst[1].write('*RST')
        inpt = self.inst[1].write('SOUR:VOLT:RANG 100')
        inpt = self.inst[1].write('SOUR:VOLT:ILIM 0.001')
        inpt = self.inst[1].write('SENS:CURR:NPLC ' + str(nplc))
        inpt = self.inst[1].write('SOUR:VOLT 0')
        inpt = self.inst[1].write('SYST:ZCH OFF')

        # turn on the voltage
        inpt = self.inst[0].write(':OUTP ON')
        inpt = self.inst[1].write('SOUR:VOLT:STAT ON')

        #prep for figure
        fig, ax = plt.subplots(figsize=(6,6))
        plt.ion()
        fig.show()
        fig.canvas.draw()

        full_isd_list = []
        full_ig_list = []
        full_v_list = []
        for i, v_sd in enumerate(v_sd_list):
            inpt = self.inst[1].write(':SOUR:VOLT ' + str(v_sd))
            full_isd_list.append([])
            full_ig_list.append([])
            full_v_list.append([])

            for v_g in v_g_list:
                inpt = self.inst[0].write('SOUR:VOLT:LEV ' + str(v_g))
                time.sleep(wait)
                outp_i_sd = self.inst[1].query('READ?')
                outp_i_g = self.inst[0].query('READ?')

                i_sd = float(outp_i_sd.split(',')[0][:-1])
                i_g = float(outp_i_g)

                full_isd_list[i].append(i_sd)
                full_ig_list[i].append(i_g)
                full_v_list[i].append(v_g)

                #plot iv
                ax.clear()
                for volt, curr_sd in zip(full_v_list, full_isd_list):
                    ax.plot(volt, np.absolute(curr_sd), color='red')

                for volt, curr_g in zip(full_v_list, full_ig_list):
                    ax.plot(volt, np.absolute(curr_g), color='blue')

                ax.set_xlabel('V_{G} [V]')
                ax.set_ylabel('I_SD/GD [A]')
                ax.set_yscale('log')
                ax.set_title(filename)
                fig.canvas.draw()

        inpt = self.inst[0].write('OUTP OFF')
        inpt = self.inst[1].write(':SOUR:VOLT:STAT OFF')

        df_isd = pd.DataFrame(full_isd_list).T
        df_isd.columns = ['Isd_Vsd'+str(int(v_sd)) for v_sd in v_sd_list]

        df_ig = pd.DataFrame(full_ig_list).T
        df_ig.columns = ['Ig_Vsd'+str(int(v_sd)) for v_sd in v_sd_list]

        df_all = pd.concat([df_isd, df_ig], axis=1)
        df_all['Vg'] = full_v_list[0]

        df_all.to_csv(path_file + '.csv')

        return df_all


class TFT(GPIB_SetUp):
    """TFT measurement using two Keithley 2400 source measure unit

    """

    smu1_adr= 'GPIB0::13::INSTR' #gate bias
    smu2_adr= 'GPIB0::14::INSTR'  #source-drain

    def __init__(self, gpib1=smu1_adr, gpib2=smu2_adr):
        GPIB_SetUp.__init__(self, gpib1, gpib2)
        self.confirm_inst(self.info[0], '2400')
        self.confirm_inst(self.info[1], '2400')

    def handler(self, singal, frame):
        """Catch interrupt button on Jupyter"""
        self.inst[0].write('*RST')
        self.inst[0].write(':DISP:TEXT:DATA "Aborted"')
        self.inst[0].write(':DISP:TEXT:STAT ON')

        self.inst[1].write('*RST')
        self.inst[1].write(':DISP:TEXT:DATA "Aborted"')
        self.inst[1].write(':DISP:TEXT:STAT ON')
        self.inst[1].write(':SYST:BEEP 1000, 0.5')
        time.sleep(0.6)
        self.inst[1].write(':SYST:BEEP 784, 0.5')
        print 'Interrupted by user'
        sys.exit(1)

    def meas_output(self, path, filename, v_start=0., v_end=100., v_step=5.,
                    v_g_list=np.linspace(0., 100., 6.),
                    reverse=True, cmpl=0.1, nplc=6,
                    waiting_time=0.01):

        """ measure output characteristic

        Args:
        path: string, path of directory
        filename: string, filename
        v_start: float, V_SD start voltage [V]
        v_end: float, V_SD end voltage [V]
        v_step: float, V_SDvoltage increment [V]
        v_g_list: list of float, V_G list [V]
        sdel: float, source deley [s], def=0.05
        cmpl: float, compliance current [A], def=0.1
        nplc: float, number of power line cycles (integration time), def=6
        waiting_time:, float, waiting time after gate bias is set

        Ret: df: DataFrame,
        """

        #stop when interrupt
        signal.signal(signal.SIGINT, self.handler)

        path_file, filename = self.confirm_unique_name(path, filename)

        trg_cnt = round(abs(v_start - v_end) / v_step + 1)

        nplc_repeat = int(nplc)/10 + 1
        if nplc_repeat >= 2:
            nplc = 10
        print 'nplc repeat: {}'.format(nplc_repeat)

        #set v_sd list_
        if reverse:
            v_sd_list = np.concatenate((
                np.linspace(v_start, v_end, trg_cnt),
                np.linspace(v_end, v_start, trg_cnt)),
                axis=0)

        else:
            v_sd_list = np.linspace(v_start, v_end, trg_cnt)

        # setup inst[0] (K2400)
        self.inst[0].timeout = int(2000)
        inpt = self.inst[0].write('*RST')
        inpt = self.inst[0].write(':DISP:TEXT:STAT OFF')
        inpt = self.inst[0].write(':SOUR:FUNC VOLT')
        inpt = self.inst[0].write(':SOUR:VOLT:MODE FIXED')
        inpt = self.inst[0].write(':SOUR:VOLT:RANG 120')
        inpt = self.inst[0].write(':SOUR:VOLT:LEV 0')
        inpt = self.inst[0].write(':SENS:CURR:PROT ' + str(cmpl))
        inpt = self.inst[0].write(':SENS:CURR:NPLC ' + str(nplc))
        inpt = self.inst[0].write(':SENS:FUNC "CURR"')
        inpt = self.inst[0].write(':FORM:ELEM CURR')

        # setup inst[1]
        self.inst[1].timeout = int(2000)
        inpt = self.inst[1].write('*RST')
        inpt = self.inst[1].write(':DISP:TEXT:STAT OFF')
        inpt = self.inst[1].write(':SOUR:FUNC VOLT')
        inpt = self.inst[1].write(':SOUR:VOLT:MODE FIXED')
        inpt = self.inst[1].write(':SOUR:VOLT:RANG 120')
        inpt = self.inst[1].write(':SOUR:VOLT:LEV 0')
        inpt = self.inst[1].write(':SENS:CURR:PROT ' + str(cmpl))
        inpt = self.inst[1].write(':SENS:CURR:NPLC ' + str(nplc))
        inpt = self.inst[1].write(':SENS:FUNC "CURR"')
        inpt = self.inst[1].write(':FORM:ELEM CURR')

        # turn on the voltage
        inpt = self.inst[0].write(':OUTP ON')
        inpt = self.inst[1].write(':OUTP ON')

        #prep for figure
        fig, ax = plt.subplots(1, 2, figsize=(8,4))
        plt.ion()
        plt.tight_layout()
        fig.show()
        fig.canvas.draw()

        full_isd_list = []
        full_igd_list = []
        full_vsd_list = []
        for i, v_g in enumerate(v_g_list):
            inpt = self.inst[0].write(':SOUR:VOLT:LEV ' + str(v_g))
            full_isd_list.append([])
            full_igd_list.append([])
            full_vsd_list.append([])

            for v_sd in v_sd_list:
                inpt = self.inst[1].write('SOUR:VOLT:LEV ' + str(v_sd))
                time.sleep(waiting_time)

                i_sd, i_gd = 0., 0.
                for rep in range(nplc_repeat):
                    outp1 = self.inst[0].query('READ?')
                    outp2 = self.inst[1].query('READ?')
                    i_gd += float(outp1)
                    i_sd += float(outp2)


                full_isd_list[i].append(i_sd)
                full_igd_list[i].append(i_gd)
                full_vsd_list[i].append(v_sd)

                #plot iv
                ax[0].clear()
                for volt, curr in zip(full_vsd_list, full_isd_list):
                    ax[0].plot(volt, np.absolute(curr))
                ax[0].set_xlabel('V_SD [V]')
                ax[0].set_ylabel('I_SD [A]')
                ax[0].set_title(filename + ' Vsd')
                ax[0].set_yscale('log')

                ax[1].clear()
                for volt, curr in zip(full_vsd_list, full_igd_list):
                    ax[1].plot(volt, np.absolute(curr))
                ax[1].set_xlabel('V_GD [V]')
                ax[1].set_ylabel('I_{SD} [A]')
                ax[1].set_title(filename + ' Vgd')
                ax[1].set_yscale('log')

                fig.canvas.draw()

                """print "Vg = {0:0.1f}, Vsd = {1:0.1f}, I_sd = {2:0.3e}".format(
                    v_g, v_sd, i_sd
                )"""

        inpt = self.inst[0].write('OUTP OFF')
        inpt = self.inst[1].write('OUTP OFF')

        df_isd = pd.DataFrame(full_isd_list).T
        df_isd.columns = ['Isd_Vg'+str(int(v_g)) for v_g in v_g_list]

        df_ig = pd.DataFrame(full_ig_list).T
        df_ig.columns = ['Ig_Vg'+str(int(v_g)) for v_g in v_g_list]

        df_all = pd.concat([df_isd, df_ig], axis=1)
        df_all['Vsd'] = full_vsd_lsit[0]

        df_all.to_csv(path_file + '.csv')

        self.inst[0].write(':DISP:TEXT:DATA "Done"')
        self.inst[0].write(':DISP:TEXT:STAT ON')

        self.inst[1].write(':DISP:TEXT:DATA "Done"')
        self.inst[1].write(':DISP:TEXT:STAT ON')
        self.inst[1].write(':SYST:BEEP 1800,1.0')

        return df

    def meas_transfer(self, path, filename, v_start=-10., v_end=100.,
                      v_step=5., v_sd_list=[20.,50.,80.],
                      reverse=True, cmpl=0.01, nplc=6, wait=0.01):

        """

        :param path: string, path of directory
        :param filename: string, filename
        :param v_start: float, V_G start=-10. [V]
        :param v_end: float, V_G end=100. [V]
        :param v_step: float, V_G step=5. [V]
        :param v_sd_list: list of float, V_SD list=[20., 50., 80.] [V]
        :param reverse: boolan, True
        :param cmpl: float, compliance=0.01 [A]
        :param nplc: float, nplc=6
        :param wait: waiting time after voltage is set = 0.01 [s]
        :return: df: DataFrame
        """

        #stop when interrupted
        signal.signal(signal.SIGINT, self.handler)

        path_file, filename = self.confirm_unique_name(path, filename)

        trg_cnt = round(abs(v_start - v_end) / v_step + 1)

        nplc_repeat = int(nplc)/10 + 1
        if nplc_repeat >= 2:
            nplc = 10
        print 'nplc repeat: {}'.format(nplc_repeat)

        #set v_sd list_
        if reverse:
            v_g_list = np.concatenate((
                np.linspace(v_start, v_end, trg_cnt),
                np.linspace(v_end, v_start, trg_cnt)),
                axis=0)

        else:
            v_g_list = np.linspace(v_start, v_end, trg_cnt)

        # setup inst[0]
        self.inst[0].timeout = int(2000)
        inpt = self.inst[0].write('*RST')
        inpt = self.inst[0].write(':DISP:TEXT:STAT OFF')
        inpt = self.inst[0].write(':SOUR:FUNC VOLT')
        inpt = self.inst[0].write(':SOUR:VOLT:MODE FIXED')
        inpt = self.inst[0].write(':SOUR:VOLT:RANG 120')
        inpt = self.inst[0].write(':SOUR:VOLT:LEV 0')
        inpt = self.inst[0].write(':SENS:CURR:PROT ' + str(cmpl))
        inpt = self.inst[0].write(':SENS:CURR:NPLC ' + str(nplc))
        inpt = self.inst[0].write(':SENS:FUNC "CURR"')
        inpt = self.inst[0].write(':FORM:ELEM CURR')

        # setup inst[1]
        self.inst[1].timeout = int(2000)
        inpt = self.inst[1].write('*RST')
        inpt = self.inst[1].write(':DISP:TEXT:STAT OFF')
        inpt = self.inst[1].write(':SOUR:FUNC VOLT')
        inpt = self.inst[1].write(':SOUR:VOLT:MODE FIXED')
        inpt = self.inst[1].write(':SOUR:VOLT:RANG 120')
        inpt = self.inst[1].write(':SOUR:VOLT:LEV 0')
        inpt = self.inst[1].write(':SENS:CURR:PROT ' + str(cmpl))
        inpt = self.inst[1].write(':SENS:CURR:NPLC ' + str(nplc))
        inpt = self.inst[1].write(':SENS:FUNC "CURR"')
        inpt = self.inst[1].write(':FORM:ELEM CURR')

        # turn on the voltage
        inpt = self.inst[0].write(':OUTP ON')
        inpt = self.inst[1].write(':OUTP ON')

        #prep for figure
        fig, ax = plt.subplots(figsize=(6,6))
        plt.ion()
        fig.show()
        fig.canvas.draw()

        full_isd_list = []
        full_ig_list = []
        full_v_list = []
        for i, v_sd in enumerate(v_sd_list):
            inpt = self.inst[1].write(':SOUR:VOLT ' + str(v_sd))
            full_isd_list.append([])
            full_ig_list.append([])
            full_v_list.append([])

            for v_g in v_g_list:
                inpt = self.inst[0].write('SOUR:VOLT:LEV ' + str(v_g))
                time.sleep(wait)

                i_sd, i_gd = 0., 0.
                for rep in range(nplc_repeat):
                    outp_i_gd = self.inst[0].query('READ?')
                    outp_i_sd = self.inst[1].query('READ?')

                    i_sd += float(outp_i_sd)
                    i_gd += float(outp_i_gd)

                full_isd_list[i].append(i_sd)
                full_ig_list[i].append(i_gd)
                full_v_list[i].append(v_g)

                #plot iv
                ax.clear()
                for volt, curr_sd in zip(full_v_list, full_isd_list):
                    ax.plot(volt, np.absolute(curr_sd), color='red')

                for volt, curr_g in zip(full_v_list, full_ig_list):
                    ax.plot(volt, np.absolute(curr_g), color='blue')

                ax.set_xlabel('V_{G} [V]')
                ax.set_ylabel('I_SD/GD [A]')
                ax.set_yscale('log')
                ax.set_title(filename)
                fig.canvas.draw()

        inpt = self.inst[0].write('OUTP OFF')
        inpt = self.inst[1].write('OUTP OFF')

        df_isd = pd.DataFrame(full_isd_list).T
        df_isd.columns = ['Isd_Vsd'+str(int(v_sd)) for v_sd in v_sd_list]

        df_ig = pd.DataFrame(full_ig_list).T
        df_ig.columns = ['Ig_Vsd'+str(int(v_sd)) for v_sd in v_sd_list]

        df_all = pd.concat([df_isd, df_ig], axis=1)
        df_all['Vg'] = full_v_list[0]

        df_all.to_csv(path_file + '.csv')

        self.inst[0].write(':DISP:TEXT:DATA "Done"')
        self.inst[0].write(':DISP:TEXT:STAT ON')

        self.inst[1].write(':DISP:TEXT:DATA "Done"')
        self.inst[1].write(':DISP:TEXT:STAT ON')
        self.inst[1].write(':SYST:BEEP 1800,1.0')

        return df_all


class Picoammeter(GPIB_SetUp):
    PAM_ADRS = 'GPIB0::11::INSTR'

    def __init__(self, gpib_add=PAM_ADRS):
        GPIB_SetUp.__init__(self, gpib_add)
        self.confirm_inst(self.info[0], '6487')

    def meas_curr_sweep(self, path, filename, v_start, v_end, v_step,
                        rang=10, ilim=2.5e-3, nplc=6, graph=True, print_data=False):

        sns.set(style='ticks')
        path_filename, fn = self.confirm_unique_name(path, filename)

        self.inst[0].timeout = int(nplc * 60 * 1000 * 2)

        inpt = self.inst[0].write('*RST')
        inpt = self.inst[0].write('SOUR:VOLT:RANG ' + str(rang))
        inpt = self.inst[0].write('SOUR:VOLT:ILIM ' + str(ilim))
        inpt = self.inst[0].write('SENS:CURR:NPLC ' + str(nplc))

        volt_list = np.arange(v_start, v_end + v_step, v_step)
        current_list_raw = []

        for volt in volt_list:
            inpt = self.inst[0].write('SOUR:VOLT ' + str(volt))
            inpt = self.inst[0].write('SOUR:VOLT:STAT ON')
            inpt = self.inst[0].write('SYST:ZCH OFF')
            outp = self.inst[0].query('READ?')

            current = float(outp.split(',')[0][:-1])
            current_list_raw.append(current)
            if print_data:
                print volt, current

            inpt = self.inst[0].write('SOUR:VOLT:STAT OFF')

        current_list = np.array(current_list_raw)

        fit = np.polyfit(current_list, volt_list, 1)
        print 'linear fit results: %0.2e [Ohm], residue %0.2e [V]' % (fit[0], fit[1])
        resistivity = fit[0]
        fit_line = fit[0] * current_list + fit[1]

        if graph:
            f, ax = plt.subplots(figsize=(4, 4))
            ax.plot(current_list, volt_list, 'o', color='b', )
            ax.plot(current_list, fit_line, 'r')
            ax.set_xlabel('Current [A]')
            ax.set_ylabel('Voltage [V]')

        df = pd.DataFrame([volt_list, current_list], index=['Voltage', 'Current']).T

        df.to_csv(path_filename + '.csv')

        return volt_list, current_list, resistivity


class PicowithLED(Picoammeter):
    """
    Measure IV characteristics with Keithley 6487 Picoammeter and
    THORLABS DC2200 LED controller
    """

    def __init__(self, smu_adr='GPIB0::11::INSTR'):
        #Get the lengthy address of DC2200
        def find_DC2200_adr():
            rm = visa.ResourceManager()
            res_list = rm.list_resources()
            DC2200_found = False
            for res in res_list:
                if 'USB0' in res:
                    test_inst = rm.open_resource(res)
                    try:
                        out = test_inst.query('*IDN?')
                        if 'DC2200' in out:
                            DC2200_found = True
                            return res
                            break
                    except:
                        pass

            if not DC2200_found:
                try:
                    raise Exception("DC2200 not found")
                except Exception, e:
                    print e

        dc2200_adr = find_DC2200_adr()
        GPIB_SetUp.__init__(self, smu_adr, dc2200_adr)
        self.confirm_inst(self.info[0], '6487')
        self.confirm_inst(self.info[1], '2200')
        """self.K2400 = rm.open_resource(gpib_addr)
        self.K2400_info = self.K2400.query('*IDN?')
        self.confirm_inst(self.K2400_info, '2400')
        """

    def handler3(self, singal, frame):
        """Catch interrupt button on Jupyter"""
        self.inst[0].write('*RST')
        self.inst[1].write('*RST')
        print 'Interrupted by User'
        sys.exit(1)

    def measure_IV_LED(
            self, path, filename, v_start, v_end, v_step, light_list, rang=10,
            ilim=2.5e-3, nplc=6, graph=True, print_data=False):

        signal.signal(signal.SIGINT, self.handler3)

        self.inst[1].write('*RST') #Constant brightness mode
        self.inst[1].write(':SOUR:MODE 2') #Constant brightness mode
        self.inst[1].write(':SOUR:CBR 0') #Birhgtness = 0
        self.inst[1].write(':OUTP:STATE 1') #Birhgtness = 0

        df_list=[]

        for light in light_list:
            self.inst[1].write(':SOUR:CBR ' + str(light))

            filename_light = filename + '_LED' + str(light).zfill(3)

            out_df = self.meas_curr_sweep(
                path=path, filename=filename_light, v_start=v_start,
                v_end=v_end, v_step=v_step, rang=rang, ilim=ilim, nplc=nplc,
                graph=graph, print_data=print_data)

            df_list.append(out_df)


        self.inst[1].write(':OUTP:STATE 0') #turn off the output

        return df_list


class KE2602(GPIB_SetUp):
    cnsi_addr = 'GPIB0::26::INSTR'

    def __init__(self, cnsi_addr):
        GPIB_SetUp.__init__(self, gpib_addr)
        self.confirm_inst(self.info[0], "2602")

    def handler2(self, singal, frame):
        """Catch interrupt button on Jupyter"""
        self.inst.write('smua.reset()')
        self.df.to_csv(self.filename + '.csv')
        print 'Interrupted'
        sys.exit(1)

    def test(self):
        print 'tttt'

    def iv_sweep_core(self, v_start, v_end, step_num, bottom_anode=False,
                      sdel=0.1, cmpl=0.1, nplc=1):
        """do I-V sweep on Keithley 2602 source meter

        Args:
        v_start: float, start voltage [V]
        v_end: float, end voltage [V]
        step_num: integer, number of the step
        bottom_anode: boolan, if true, the bottom electrode is anode (+)
        sdel: float, source deley [s]
        cmpl: float, compliamce current [A]
        nplc: float, number of power line cycles (0.001 to 25)
              1NPLC = 1/60 [1/Hz] = 0.0167 sec

        """

        sweep_time = (sdel + nplc * 0.0167) * step_num
        self.inst[0].timeout = int(sweep_time * 1000 * 2)  # double of the sweep time, to be safe

        if not bottom_anode:
            v_start = -v_start
            v_end = - v_end

        voltage = np.linspace(v_start, v_end, step_num)

        inpt = self.inst[0].write('smua.reset()')
        inpt = self.inst[0].write('smua.measure.nplc = ' + str(nplc))
        inpt = self.inst[0].write('smua.source.limiti = ' + str(cmpl))
        inpt = self.inst[0].write('SweepVLinMeasureI(smua, %s, %s, %s, %s)' \
                               % (str(v_start), str(v_end), str(sdel), str(step_num)))

        output = self.inst[0].query('printbuffer(1, %s, smua.nvbuffer1.readings)' % str(step_num))

        current = np.array(map(float, output.split(', ')))

        if not bottom_anode:
            current = -current

        return voltage, current

    def meas_iv(self, path, filename, v_start=1.3, v_end=-1., step=.01,
                area=0.0432, bottom_anode=True, reverse=True, plot=True,
                pv_parm=True, sdel=0.1, cmpl=0.1, nplc=1):
        """do IV sweep
        

        """
        import iv_prms

        step_num = round(abs(v_start - v_end) / step + 1)
        # int(2.3/0.01) gives 299. It seems 2.3/0.01 < 230 in python!

        sns.set(style='ticks')

        if filename == 'test':
            if len(path) == 0:
                path_filename = filename

            else:
                path_filename = path + '/' + filename

            fn = filename

        else:
            path_filename, fn = self.confirm_unique_name(path, filename)

        if reverse:

            vf, cf = self.iv_sweep_core(v_start, v_end, step_num,
                                        bottom_anode, sdel, cmpl, nplc)

            vr, cr = self.iv_sweep_core(v_end, v_start, step_num,
                                        bottom_anode, sdel, cmpl, nplc)

            jf = cf * 1000 / area
            jr = cr * 1000 / area

            if pv_parm:
                parms = iv_prms.IVprm(vf, jf, area, reversed_j=False)
                print 'Foward scan\n' \
                      'Voc: %0.2f [V],' % parms.voc + \
                      'Jsc: %0.2f [mA/cm2],' % parms.jsc + \
                      'FF: %0.2f [-],' % parms.ff + \
                      'PCE: %0.2f' % parms.pce + ' [%],' + \
                      'Rs: %0.2f [Ohm/cm2],' % parms.rs + \
                      'Rsh: %0.2f [Ohm/cm2]' % parms.rsh

                parms = iv_prms.IVprm(vr, jr, area, reversed_j=False)
                print 'Rerverse scan\n' \
                      'Voc: %0.2f [V],' % parms.voc + \
                      'Jsc: %0.2f [mA/cm2],' % parms.jsc + \
                      'FF: %0.2f [-],' % parms.ff + \
                      'PCE: %0.2f' % parms.pce + ' [%],' + \
                      'Rs: %0.2f [Ohm/cm2],' % parms.rs + \
                      'Rsh: %0.2f [Ohm/cm2]' % parms.rsh

            if plot:
                f, ax = plt.subplots(figsize=(4, 4))
                ax.plot(vf, jf, label='foward', marker='o')
                ax.plot(vr, jr, label='reverse', marker='o')
                ax.set_xlabel('voltage [V]')
                ax.set_ylabel('current density [mA/cm2]')
                ax.legend(loc='best')
                ax.axhline(0, color='black')
                ax.axvline(0, color='black')
                ax.set_ylim(-25, 25)

            df = pd.DataFrame([vf, jf, vr, jr],
                              index=('v_foward', 'j_foward',
                                     'v_reverse', 'j_reverse')).T

            df.to_csv(path_filename + '.csv')

            return df

        else:
            vf, cf = self.iv_sweep_core(v_start, v_end, step_num,
                                        bottom_anode, sdel, cmpl, nplc)

            jf = cf * 1000 / area

            if pv_parm:
                parms = iv_parms.IVparam(vf, jf, area, reversed_j=False)
                print 'Foward scan\n' \
                      'Voc: %0.2f [V],' % parms.voc + \
                      'Jsc: %0.2f [mA/cm2],' % parms.jsc + \
                      'FF: %0.2f [-],' % parms.ff + \
                      'PCE: %0.2f' % parms.pce + ' [%],' + \
                      'Rs: %0.2f [Ohm/cm2],' % parms.rs + \
                      'Rsh: %0.2f [Ohm/cm2]' % parms.rsh

            if plot:
                f, ax = plt.subplots(figsize=(4, 4))
                ax.plot(vf, jf, marker='o')
                ax.set_xlabel('voltage [V]')
                ax.set_ylabel('current density [mA/cm2]')
                ax.axhline(0, color='black')
                ax.axvline(0, color='black')
                ax.set_ylim(-25, 25)

            df = pd.DataFrame([vf, jf], index=('v_foward', 'j_foward')).T

            df.to_csv(path_filename + '.csv')

            return df


    def meas_tpc(self, filename, area=0.0432, bias=0.0, waittime=.1, nplc=1.,
                 cmpl=.1):
        print """print magic words
        %load_ext autoreload
        %autoreload 2
        %matplotlib nbagg"""

        signal.signal(signal.SIGINT, self.handler2)
        self.filename = filename

        start_time = datetime.datetime.now()
        self.inst[0].timeout = 1000
        inpt = self.inst[0].write('smua.reset()')
        inpt = self.inst[0].write('smua.measure.nplc = ' + str(nplc))
        inpt = self.inst[0].write('smua.source.limiti = ' + str(cmpl))
        inpt = self.inst[0].write('smua.source.levelv = ' + str(bias))
        inpt = self.inst[0].write('smua.source.output = smua.OUTPUT_ON')

        f, ax = plt.subplots(figsize=(4, 4))
        plt.tight_layout()
        plt.ion()

        f.show()
        f.canvas.draw()

        self.df = pd.DataFrame([[.0, .0]], columns=['time', 'current'])
        while True:
            self.inst[0].write('smua.nvbuffer1.clear()')
            ax.clear()
            now = datetime.datetime.now()
            elasped = now - start_time

            inpt = self.inst[0].write('smua.measure.i(smua.nvbuffer1)')
            current_now = self.inst[0].query(
                'printbuffer(1, 1, smua.nvbuffer1.readings)')

            j_now = float(current_now) * 1000 / area  # [A] to [mA/cm2]

            try:
                df_now = pd.DataFrame(
                    [[elasped.total_seconds(), j_now]],
                    columns=['time', 'current'])

                self.df = self.df.append(df_now, ignore_index=True)
                ax.plot(self.df['time'], self.df['current'])
                ax.set_ylabel('Current Density [mA/cm2]')
                ax.set_xlabel('time [s]')
                f.canvas.draw()
                time.sleep(waittime)

            except ValueError:
                pass


        return self.df

    def meas_tpv(self, start_bias=0.0, nplc=.1, cmpl=.1):
        print """print magic words
        %load_ext autoreload
        %autoreload 2
        %matplotlib nbagg"""

        bais_now = start_bias

        start_time = datetime.datetime.now()
        inpt = self.inst[0].write('smua.reset()')
        inpt = self.inst[0].write('smua.measure.nplc = ' + str(nplc))
        inpt = self.inst[0].write('smua.source.limiti = ' + str(cmpl))
        inpt = self.inst[0].write('smua.source.levelv = ' + str(bias_now))
        inpt = self.inst[0].write('smua.source.output = smua.OUTPUT_ON')

        while True:
            now = datetime.datetime.now()
            elasped = now - start_time
            try:
                current_now = self.inst[0].query('smua.measure.i()')

                if current_now < 0:
                    bais_now += .01
                    inpt = self.inst[0].write('smua.source.levelv = ' \
                                           + str(bias_now))
                    print now, bias_now

                else:
                    bias_now -= .01
                    inpt = self.inst[0].write('smua.source.levelv = ' \
                                           + str(bias_now))
                    print now, bias_now

                time.sleep(waittime)

            except KeyboardInterrupt:
                print 'turned off'
                inpt = self.inst[0].write('smua.source.output = smua.OUTPUT_OFF')

                break

    def meas_light_depen(self, v_start=1.1, delay=0.5, v_step=0.01, nplc=1.,
                         cmpl=.1, area=0.0432):
        """one-shot current measurement with designated bias

        Args:
            bias: float, [V]
            nplc: float [-]
            cmpl: float, compliance [A]
            area: float, cell area [cm2]
        """

        #measure Voc
        inpt = self.inst[0].write('smua.reset()')
        inpt = self.inst[0].write('smua.measure.nplc = ' + str(nplc))
        inpt = self.inst[0].write('smua.source.limiti = ' + str(cmpl))
        inpt = self.inst[0].write('smua.source.levelv = 0')
        inpt = self.inst[0].write('smua.source.output = smua.OUTPUT_ON')

        voltage = v_start
        point_beyond_voc = 5 #number of points to measure after zero-cross
        v_list = []
        c_list = []

        while point_beyond_voc:
            v_list.append(voltage)
            inpt = self.inst[0].write('smua.source.levelv = '  + str(voltage))
            time.sleep(delay)

            inpt = self.inst[0].write('smua.measure.i(smua.nvbuffer1)')
            current_s = self.inst[0].query(
                'printbuffer(1, 1, smua.nvbuffer1.readings)')

            current = float(current_s)
            c_list.append(current)
            print voltage, current

            if current < 0:
                point_beyond_voc -= 1

            voltage -= v_step

        inpt = self.inst[0].write('smua.source.output = smua.OUTPUT_OFF')

        #linear fit of j-v to get accurate Voc
        a, b = np.polyfit(v_list, c_list, 1)
        voc = -b/a #intercept at y=0

        #mesure Jsc
        inpt = self.inst[0].write('smua.reset()')
        inpt = self.inst[0].write('smua.measure.nplc = ' + str(nplc))
        inpt = self.inst[0].write('smua.source.limiti = ' + str(cmpl))
        inpt = self.inst[0].write('smua.source.levelv = 0')
        inpt = self.inst[0].write('smua.source.output = smua.OUTPUT_ON')

        time.sleep(3)

        inpt = self.inst[0].write('smua.measure.i(smua.nvbuffer1)')
        current_s = self.inst[0].query('printbuffer(1, 1, smua.nvbuffer1.readings)')
        current = float(current_s)

        inpt = self.inst[0].write('smua.source.output = smua.OUTPUT_OFF')

        current_density = current*1000 / area #[A] -> [mA/cm2]

        print 'jsc = 0.2f [mA/cm2], Voc = {:0.2f} [V]'.format(current_density,
                                                              voc)

        return current_density, voltage

    def mppt(self, filename, watetime=0., v_step=0.005, start_v=1.0, area=0.0432,
             nplc=1., cmpl=.1):

        PINT = 100 #incident light power (mW/cm2)

        signal.signal(signal.SIGINT, self.handler2)
        self.filename = filename

        stat_time = datetime.datetime.now()
        self.inst[0].timeout = 1000

        self.inst[0].write('smua.reset()')
        self.inst[0].write('smua.measure.nplc = ' + str(nplc))
        self.inst[0].write('smua.source.limiti = ' + str(cmpl))
        self.inst[0].write('smua.source.levelv = 0.0')
        self.inst[0].write('smua.source.output = smua.OUTPUT_ON')
        print 'here'

        f, ax = plt.subplots(1, 3, figsize=(12, 4))
        plt.tight_layout()
        plt.ion()

        f.show()
        f.canvas.draw()

        self.df = pd.DataFrame([[0., 0., 0., 0.]],
                               columns=['time', 'current', 'voltage', 'PCE']
                               )

        voltage = start_v
        PCE = 0.
        while True:
            self.inst[0].write('smua.nvbuffer1.clear()')
            ax[0].clear()
            ax[1].clear()
            ax[2].clear()

            PCE_previous = PCE

            now = datetime.datetime.now()
            elapsed = now - stat_time

            self.inst[0].write('smua.source.levelv = ' + str(voltage))
            self.inst[0].write('smua.measure.i(smua.nvbuffer1)')
            current_read = self.inst[0].query(
                'printbuffer(1, 1, smua.nvbuffer1.readings)')

            current_density = float(current_read) / area * 1000 # (mA/cm2)
            power_cm2 = -current_density * voltage #(mW/cm2)
            PCE = power_cm2 / PINT * 100 #(%)

            try:
                df_now = pd.DataFrame(
                    [[elapsed.total_seconds(), current_density, voltage, PCE]],
                    columns=['time', 'current', 'voltage', 'PCE']
                )

                self.df = self.df.append(df_now, ignore_index=True)
                ax[0].plot(self.df['time'], self.df['PCE'],)
                ax[0].set_ylabel('PCE (%)')
                ax[0].set_xlabel('time (s)')

                ax[1].plot(self.df['time'], self.df['current'], )
                ax[1].set_ylabel('current density (mA/cm2)')
                ax[1].set_xlabel('time (s)')

                ax[2].plot(self.df['time'], self.df['voltage'],)
                ax[2].set_ylabel('voltage (V)')
                ax[2].set_xlabel('time (s)')

                f.canvas.draw()
                time.sleep(watetime)

            except ValueError:
                pass

            if PCE_previous < PCE:
                voltage += v_step

            else:
                voltage -= v_step

            """optmize the voltage
            voltage_2 = voltage + v_step*5

            self.inst[0].write('smua.source.levelv = ' + str(voltage_2))
            self.inst[0].write('smua.nvbuffer1.clear()')
            self.inst[0].write('smua.measure.i(smua.nvbuffer1)')
            current_read2 = self.inst[0].query(
                'printbuffer(1, 1, smua.nvbuffer1.readings)'
            )

            current_density_2 = float(current_read2) / area * 1000 # (mA/cm2)
            power_cm2_2 = -current_density_2 * voltage_2 #(mW/cm2)
            PCE_2 = power_cm2_2 / PINT * 100 #(%)

            print PCE, PCE_2
            if PCE_2 < PCE:
                voltage -= v_step
                print 'down'

            else:
                voltage += v_step
                print 'up'
            """

        return self.df

