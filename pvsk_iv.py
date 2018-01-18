from import_all import *

DEV_AREA = 0.0432 #[cm^2] = 3.6 x 1.2 [mm^2]

def read_csvfile(filename, v_start, v_end, v_step, show_graph=True):
    
    device_name = filename.split('/')[-1].split('.')[0]
    
    ch_list = ['ch1', 'ch2', 'ch3', 'ch4', 'ch5']
    
    df = pd.read_csv(filename, sep='\t', header=None)
    df.columns = ['voltage'] + ch_list
    
    v_step_num = int(abs(v_start - v_end)/v_step)

    df_f = df[df.index<=v_step_num]
    df_fs = df_f.sort_values(['voltage']).reset_index(drop=True)
    df_fs.columns = ['voltage'] + [device_name + '_' + ch + '_f' for ch in ch_list]
    
    df_r = df[df.index>v_step_num]
    df_rs = df_r.sort_values(['voltage']).reset_index(drop=True)
    
    for ch in ch_list:
        df_fs[device_name + '_' + ch + '_r'] = df_rs[ch]
        
    if show_graph:
        f, ax = plt.subplots(1,5, figsize=(25,5))
        f.suptitle(device_name, fontsize="xx-large")
        for i, ch in enumerate(ch_list):
            for ch_name in [c for c in df_fs.columns if ch in c]:
                ax[i].plot(df_fs['voltage'], df_fs[ch_name], label=ch_name.split('_')[-1])
                ax[i].legend(loc='best')
                ax[i].set_ylim(-25, 25)
                ax[i].axhline(0, color='black')
                ax[i].axvline(0, color='black')
        
    return df_fs
                
def cal_prms(df):
    import iv_prms
    name_list = []
    voc_list = []
    jsc_list = []
    ff_list = []
    pce_list = []
    rs_list = []
    rsh_list = []
    for ch in df.columns[1:]:
        prm = iv_prms.IVprm(np.array(df['voltage']), np.array(df[ch]), DEV_AREA, reversed_j=False)
        name_list.append(ch)
        voc_list.append(prm.voc)
        jsc_list.append(prm.jsc)
        ff_list.append(prm.ff)
        pce_list.append(prm.pce)
        rs_list.append(prm.rs)
        rsh_list.append(prm.rsh)
        
    df_prm = pd.DataFrame([name_list, voc_list, jsc_list, 
                           ff_list, pce_list, rs_list, rsh_list]).T
    
    df_prm.columns = ['name', 'Voc', 'Jsc', 'FF', 'PCE', 'Rs', 'Rsh']
    
    return df_prm

def read_all(path, v_start=1.3, v_end=-1., v_step=0.01, cal_prm=True, export=True):
    import glob
    file_list = glob.glob(path + '/*.txt')
    
    for i, filename in enumerate(file_list):
        df = read_csvfile(filename, v_start, v_end, v_step)
        
        if i==0:
            df_iv = df
            
        else:
            df_iv = pd.concat([df_iv, df.drop('voltage',axis=1)], axis=1)
            
    if cal_prm:
        df_prm = cal_prms(df_iv)
    
    if export:
        df_iv.to_csv(path + '/iv_list.csv')
        df_prm.to_csv(path + '/prm_list.csv')
            
    return df_iv, df_prm
        
