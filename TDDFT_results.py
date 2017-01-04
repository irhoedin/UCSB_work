def collect_TDDFT():
    import glob
    td_list = sorted(glob.glob('*TDDFT.log'))
    f = open('TDDFT_results.csv', 'w')

    print '*' *15
    for td_file in td_list:
        norm_term = False
        error_term = False
        print '\n' + td_file
        f.write('\n' + td_file + '\n')
       
        header = 'energy [eV],energy [nm],oscillator strength'
        print header
        f.write(header + '\n')
        
        for line in open(td_file, 'r'):
            if 'Excited State' in line:
                nums = line.split(' ')
                en_ev = float(nums[17])
                en_nm = float(nums[20])
                o_str = float(nums[23].split('=')[-1])

                res = '%0.2f,%0.2f,%0.4f' %(en_ev, en_nm, o_str)
                print res
                f.write(res + '\n')
        
            if 'Normal termination' in line:
                norm_term = True

            if 'Error termination' in line:
                error_term = True

        if not norm_term:
            if error_term:
                statement = 'error termination'
                print statement
                f.write(statement + '\n')
            else:
                statement = 'not terminated'
                print statement
                f.write(statement + '\n')

            

if __name__ == '__main__':
    collect_TDDFT()
