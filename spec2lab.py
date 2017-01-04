import numpy as np
import pandas as pd
from scipy import interpolate
import matplotlib.pyplot as plt

DATA_DIR = '/spec2lab_data/'
D65 = DATA_DIR + 'D65_light.txt'
ISOCOLOR = DATA_DIR + 'isocolor_xyz.txt'

def spec2colormaps(wl_sample, data_sample, light_source=D65,
                         trans=False, fig=True, color_conc=1):
    """ Convert absorption spectrum to (X, Y, Z), (L, a, b), and (red, green, blue).
    Require 'isocolor_xyz.txt'.
    
    Args:
    wl_sample: Panda Serise, wavelength of abosorption spectrum
    data_sample: Panda Serise, absorption or transmittance
    light_source: string, adrress and filename of light source file.
                  light source file contains wavelength data in colmun 0,
                  light source power data in column 1.
                  The first line is a header, and each figures is separated by tab(\t).
                  Default: 'D65_light.txt'
    trans: boolan, if true, "data_sample" is treated as transmittance
    fig: boolan, if true, figures of transmittance and light spectrum is shown
    color_conc: float, tune this figures if the rgb is too dark for light to be shown in
    screens.
    
    Retrun:
    ((X, Y, Z),
     (L, a, b, c),
     (red, blue, green),
     (red_cc, blue_cc, green_cc)) 

    Refernces:
    http://www.ns.kogakuin.ac.jp/~ct13050/johogaku/2-6.spectral_analysis_of_color_light.pdf
    (Spectrum to XYZ)
    http://w3.kcua.ac.jp/~fujiwara/infosci/colorspace/colorspace2.html (XYZ to RGB)
    http://www.easyrgb.com/index.php?X=MATH&H=01#text1 (XYZ to RGB)
    http://www.konicaminolta.jp/instruments/knowledge/color/part1/07.html (Lab color space)
    """

    (X, Y, Z) = spec2XYZ(wl_sample, data_sample, light_source, trans, fig)
    (L, a, b, c) = XYZ2Lab(X, Y, Z)
    (red, green, blue) = XYZ2RGB(X, Y, Z)

    if trans:
        data_sample_cc = data_sample * 10**(color_conc)
    else:
        data_sample_cc = data_sample * color_conc

    (X_cc, Y_cc, Z_cc) = spec2XYZ(wl_sample, data_sample_cc, light_source, trans, fig)
    (red_cc, green_cc, blue_cc) = XYZ2RGB(X_cc, Y_cc, Z_cc)

    return ((X, Y, Z),
             (L, a, b, c),
             (red, green, blue),
             (red_cc, green_cc, blue_cc))

def spec2XYZ(wl_sample, data_sample, light_source_data=D65, trans=False, fig=False):
    """ Convert absorption spectrum to (X, Y, Z).
    Require 'isocolor_xyz.txt'.
    
    Args:
    wl_sample: Panda Serise, wavelength of abosorption spectrum
    data_sample: Panda Serise, absorption or transmittance
    light_source: string, adrress and filename of light source file.
                  light source file contains wavelength data in colmun 0,
                  light source power data in column 1.
                  The first line is a header, and each figures is separated by tab(\t).
                  Default: 'D65_light.txt'
    trans: boolan, if true, "data_sample" is treated as transmittance
    fig: boolan, if true, figures of transmittance and light spectrum is shown
    Retrun: (X, Y, Z)
    """

    #read light source data
    light_source = pd.read_csv(light_source_data, header=0, sep='\t')
    wl_ls = light_source.iloc[:,0]
    spec_ls = light_source.iloc[:,1]
    
    isocolor = pd.read_csv(ISOCOLOR, header=0, sep='\t')
    wl_5nm = isocolor["nm"]
    x_bar = isocolor["X2"]
    y_bar = isocolor["Y2"]
    z_bar = isocolor["Z2"]
    
    #interpolate light source data
    f2 = interpolate.interp1d(wl_ls, spec_ls)
    spec_new = f2(wl_5nm)
    if fig:
        fig, ax = plt.subplots(2, figsize=(5,10))
        ax[1].plot(wl_5nm, spec_new, 'o-')
        ax[1].set_title('Light Source')
        ax[1].set_ylabel('Light Power')
    
    #interpolate sample data
    if trans:
        trans = data_sample
    else:
        trans = 10**(-data_sample)
    
    f = interpolate.interp1d(wl_sample, trans)
    trans_new = f(wl_5nm) #original data
    if fig:
        ax[0].plot(wl_5nm, trans_new, 'o-')
        ax[0].set_title('Sample Transmittance')
        ax[0].set_ylabel('Transmittance')

    #calc X, Y, Z, and K
    int_ =np.trapz(spec_new * y_bar, dx=5)
    K = 100/np.trapz(spec_new * y_bar, dx=5)
    X = np.trapz(spec_new * x_bar * trans_new, dx=5) * K
    Y = np.trapz(spec_new * y_bar * trans_new, dx=5) * K
    Z = np.trapz(spec_new * z_bar * trans_new, dx=5) * K

    return (X, Y, Z)


def XYZ2Lab(X, Y, Z, whitepoint=(95.5, 100, 108.89)):
    """convert XYZ color map to L*a*b* color map.
    
    whitepoint defalut value is D65.
    """

    #White Point: D65
    Xn = whitepoint[0]
    Yn = whitepoint[1]
    Zn = whitepoint[2]

    L = 116 * (Y/Yn)**(1.0/3.0) - 16
    a = 500 * ((X/Xn)**(1.0/3.0) - (Y/Yn)**(1.0/3.0))
    b = 200 * ((Y/Yn)**(1.0/3.0) - (Z/Zn)**(1.0/3.0))
    c = (a**2 + b**2)**0.5
    
    return (L, a, b, c)


def XYZ2RGB(X, Y, Z):
    """convert XYZ color map to RGB color map
    
    For transfer matrix list, refer
    http://www.brucelindbloom.com/index.html?Eqn_RGB_XYZ_Matrix.html
    """
    
    #sRGB D65 Matrix
    T_MATRIX = np.matrix( [[3.240970, -1.537383, -0.498611],
                          [-0.969244, 1.875968, 0.041555],
                          [0.055630, -0.203977, 1.056972]])

    x_100, y_100, z_100 = X/100, Y/100, Z/100
    xyz_matrix = np.matrix([[x_100],[y_100],[z_100]])
    rgb_matrix = T_MATRIX * xyz_matrix

    red = rgb_matrix[0,0]
    green = rgb_matrix[1,0]
    blue = rgb_matrix[2,0]

    return (red, green, blue)


def excel2lab(excel_name, color_conc=1):
    """read excel file with UV data collection macro and
    output csv file of Lab data list.

    In "UV data" sheet, wavelength and absorption data are stored.
    The first row contains titles.

    Ret:
    (DataFrame, color_map_list)
    """

    data = pd.read_excel(excel_name, sheetname='UV data', header=0)
    Lab_list = []
    f, ax = plt.subplots()
    name_list = data.columns[1:]
    for name in name_list:
        colors = spec2colormaps(data['wavelength'], data[name], fig=False,
                                color_conc=color_conc)
        (L, a, b, c) = colors[1]
        ax.plot(data['wavelength'], data[name], label=name)
        print '%s, %f, %f, %f' %(name, L, a, b)
        Lab_list.append((L, a, b, c))
        
    Lab_df = pd.DataFrame(Lab_list, index=name_list, columns = ['L*', 'a*', 'b*', 'c*'])
    csv_name = excel_name.split('.')[0] + '.csv'
    Lab_df.to_csv(csv_name)
    
    return Lab_df, colors


if __name__ == '__main__': 
    abs_data = pd.read_csv('G8M_abs.txt', header=0, sep='\t')
    wl = abs_data.iloc[:,0]
    absorbance = abs_data.iloc[:,1]

    ref_data = pd.read_csv('D65_light.txt', header=0, sep='\t')
    wl_ls = ref_data.iloc[:,0]
    spec_ls = ref_data.iloc[:,1]

    conv_spectrum_to_lab(wl, absorbance,wl_ls, spec_ls)
