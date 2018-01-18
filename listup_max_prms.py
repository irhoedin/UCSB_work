from import_all import *
import glob

def list_up_max_prms():
    csv_list = glob.glob('*_prm.csv')
    print 'csv list'
    print csv_list

    prm_list = []
    for csv_file in csv_list:
        each_prm_list = []
        df = pd.read_csv(csv_file, index_col=0).T
        df_sorted = df.sort_values('PCE', ascending=False)
        
        max_ch_vals = df_sorted.iloc[0]

        name = max_ch_vals.name.split('_')[0]
        each_prm_list.append(name)
        
        ch = max_ch_vals.name.split('_')[-1]
        each_prm_list.append(ch)
        
        for i in range(4):
            each_prm_list.append(max_ch_vals[i])
            
        prm_list.append(each_prm_list)
        
    prm_df = pd.DataFrame(prm_list, columns=['ID', 'max_ch', 'Voc', 'Jsc', 'FF', 'PCE'])
    print prm_df

    prm_df.to_csv('max_vals.txt')

    return prm_df

if __name__ == '__main__':
    max_list = list_up_max_prms()
    raw_input('press any key to terminate')
