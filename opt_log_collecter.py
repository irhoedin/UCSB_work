import glob
from datetime import datetime

def read_logs():
    now = datetime.now().strftime("%Y%m%d_%H%M%S")

    header = 'Filename, Stoichiometry, HOMO [eV], LUMO [eV], HOMO-LUMO gap[eV], Dipole[D]\n' 
    f = open('Opt_results.csv', 'a')
    print '\n' + '*'*15
    print header.rstrip()
    f.write(header)

    log_list = sorted(glob.glob('*.log'))

    for log_file in log_list:
        filename = log_file.split('/')[-1]
        opt = False
        error = False
        lumo_flag = True
        for line in open(log_file, 'r'):
            if 'Optimization completed' in line:
                opt = True

            if 'Error termination' in line:
                error = True
                error_line = line.rstrip() + '\n'

            if opt:


                if 'Stoichiometry' in line:
                    stoichiometry = line.split(' ')[-1].rstrip()

                if 'Alpha  occ.' in line:
                    homo_Hatree = line.split(' ')[-1]
                    homo_ev = float(homo_Hatree) * 27.2114 #Hartree to eV

                if ('Alpha virt.' in line) & lumo_flag:
                    lumo_Hartree = line.split ('  ')[1]
                    lumo_ev = float(lumo_Hartree) * 27.2114 #Hartree to eV
                    lumo_flag = False

                if 'Tot=' in line:
                    dipole_str = line.split(' ')[-1]
                    dipole = float(dipole_str)

        if opt:
            result = '%s, %s, %0.2f, %0.2f, %0.2f, %0.2f\n' \
                        %(filename, stoichiometry, homo_ev, lumo_ev, (lumo_ev - homo_ev), dipole)
            print result.rstrip() 
            f.write(result)

        elif error:
            print filename + ', ' + error_line.rstrip() 
            f.write(filename + ', ' + error_line)

        else:
            result = filename  + ', not optimized yet\n'
            print result.rstrip() 
            f.write(result)

    f.close()

    print '*' * 15 + '\n'

if __name__ == '__main__':
    read_logs()
            
