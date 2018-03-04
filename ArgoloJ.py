'''
This macro is part of the MRI ArgoJ Tool Set Verion 2.1 developed by Marc LARTAUD MRI PHIV
and OMERO.metrics by Julio Mateos Langerak MRI IGH

Copyright'''


from ij import IJ, ImagePlus
from ij import WindowManager as wm
from ij.plugin.frame import RoiManager
from ij.plugin.filter import ParticleAnalyzer
from ij.measure import Measurements
from ij.measure import ResultsTable
from ij.process import LUT

from math import sqrt
from jarray import zeros

HOMOGENEITY_RADIUS = 1
HOMOGENEITY_THRESHOLD = 'Otsu'
HOMOGENEITY_ACCEPTANCE_THRESHOLD = 70
REMOVE_CROSS = True # Remove cross from the homogeneity image

# seuil_calibration=newArray("Li",100,255);
# seuil_homogeneite=newArray("Otsu",100,255);
# seuil_coalignement_tot=newArray("Default",100,255);
# seuil_coalignement=newArray("Yen",100,255);
# seuil_dispersion=newArray("Minimum",100,255);
# seuil_resolution=newArray("Default",100,255);
# seuil_geometrie=newArray("Default",100,255);
# radius_calibration=1;
# radius_homogeneite=1;
# radius_coalignement=2;
# radius_dispersion=3;
# radius_resolution=20;
# radius_linearite=2;
# taille_calibration=newArray(50,500);
# taille_homogeneite=newArray(20,100);
# taille_coalignement=newArray(0.5,10,1);
# taille_resolution=newArray(2,10000);
# taille_linearite=newArray(200,1000000);
#

def compute_mean(values):
    return sum(values)/len(values)


def compute_median(values):
    values = sorted(values)
    index = (len(values) - 1) // 2
    if (len(values) % 2):
        return values[index]
    else:
        return (values[index] + values[index + 1])/2.0


def compute_std_dev(values, mean=None):
    if not mean:
        mean = compute_mean(values)
    s = 0
    for value in values:
        s += pow(value - mean, 2)
    return sqrt(s / float(len(values) -1))


def analyze_homogeneity(image_title):
    IJ.selectWindow(image_title)
    raw_imp = IJ.getImage()
    IJ.run(raw_imp, "Duplicate...", "title=Homogeneity duplicate")
    IJ.selectWindow('Homogeneity')
    hg_imp = IJ.getImage()

    # Get a 2D image
    if hg_imp.getNSlices() > 1:
        IJ.run(hg_imp, "Z Project...", "projection=[Average Intensity]")
        hg_imp.close()
        IJ.selectWindow('MAX_Homogeneity')
        hg_imp = IJ.getImage()
        hg_imp.setTitle('Homogeneity')

    # Blur and BG correct the image
    IJ.run(hg_imp, 'Gaussian Blur...', 'sigma=' + str(HOMOGENEITY_RADIUS) + ' stack')

    # Detect the spots
    IJ.setAutoThreshold(hg_imp, HOMOGENEITY_THRESHOLD + " dark")
    rm = RoiManager(True)
    table = ResultsTable()
    pa = ParticleAnalyzer(ParticleAnalyzer.ADD_TO_MANAGER,
                          ParticleAnalyzer.EXCLUDE_EDGE_PARTICLES,
                          Measurements.AREA, # measurements
                          table, # Output table
                          0, # MinSize
                          500, # MaxSize
                          0.0, # minCirc
                          1.0) # maxCirc
    pa.setHideOutputImage(True)
    pa.analyze(hg_imp)

    areas = table.getColumn(table.getHeadings().index('Area'))

    median_areas = compute_median(areas)
    st_dev_areas = compute_std_dev(areas, median_areas)
    thresholds_areas = (median_areas - (2 * st_dev_areas), median_areas + (2 * st_dev_areas))

    roi_measurements = {'integrated_density': [],
                        'max': [],
                        'area': []}
    IJ.setForegroundColor(0, 0, 0)
    for roi in rm.getRoisAsArray():
        hg_imp.setRoi(roi)
        if REMOVE_CROSS and hg_imp.getStatistics().AREA > thresholds_areas[1]:
            rm.runCommand('Fill')
        else:
            roi_measurements['integrated_density'].append(hg_imp.getStatistics().INTEGRATED_DENSITY)
            roi_measurements['max'].append(hg_imp.getStatistics().MIN_MAX)
            roi_measurements['integrated_densities'].append(hg_imp.getStatistics().AREA)

        rm.runCommand('Delete')

    measuremnts = {'mean_integrated_density': compute_mean(roi_measurements['integrated_density']),
                   'median_integrated_density': compute_median(roi_measurements['integrated_density']),
                   'std_dev_integrated_density': compute_std_dev(roi_measurements['integrated_density']),
                   'mean_max': compute_mean(roi_measurements['max']),
                   'median_max': compute_median(roi_measurements['max']),
                   'std_dev_max': compute_std_dev(roi_measurements['max']),
                   'mean_area': compute_mean(roi_measurements['max']),
                   'median_area': compute_median(roi_measurements['max']),
                   'std_dev_area': compute_std_dev(roi_measurements['max']),
                   }

    # generate homogeinity image
    # calculate interpoint distance in pixels
    nr_point_columns = int(sqrt(len(measuremnts['mean_max'])))
    # TODO: This is a rough estimation that does not take into account margins or rectangular FOVs
    inter_point_dist = hg_imp.getWidth() / nr_point_columns
    IJ.run(hg_imp, "Maximum...", "radius="+(inter_point_dist*1.22))
    # Normalize to 100
    IJ.run(hg_imp, "Divide...", "value=" + max(roi_measurements['max'] / 100))
    IJ.run(hg_imp, "Gaussian Blur...", "sigma=" + (inter_point_dist/2))
    hg_imp.getProcessor.setMinAndMax(0, 255)

    # Create a LUT based on a predefined threshold
    red = zeros(256, 'b')
    green = zeros(256, 'b')
    blue = zeros(256, 'b')
    acceptance_threshold = HOMOGENEITY_ACCEPTANCE_THRESHOLD * 256 / 100
    for i in range(256):
        red[i] = (i - acceptance_threshold)
        green[i] = (i)
    homogeneity_LUT = LUT(red, green, blue)
    hg_imp.setLut(homogeneity_LUT)

    return hg_imp, measuremnts



origid=getImageID();
Stack.getDimensions(width, height, channels, slices, frames);
getPixelSize(unit, pixelWidth, pixelHeight);
inter_point=20/pixelWidth; //Distance entre points

run("Maximum...", "radius="+(inter_point*1.22)); // taille du filtre diagonale entre points
run("Duplicate...", "title=temp duplicate");
run("32-bit");
getStatistics(area, mean, min, max, std, histogram);
run("Divide...", "value="+max/100); //Normalisation en pourcentage
getStatistics(area, mean, min, max, std, histogram);
std_homo=std;
close();
selectWindow("homogeneite");
run("Gaussian Blur...", "sigma="+(inter_point/2));// taille du filtre diagonale sur 2
                                                                                    // 10 classes de valeurs
run("32-bit");
getStatistics(area, mean, min, max, std, histogram);
run("Divide...", "value="+max); //--> valeurs de 0 a 1
run("Multiply...", "value=10"); //--> valeurs de 0 a 10
run("Conversions...", " ");
run("8-bit");
getStatistics(area, mean, min, max, std, histogram);
print("Deviation standard normalisee de l homogeneite: "+std_homo); // calcul sur des valeurs de 1 a 10

run("Multiply...", "value=25.5");
run("Conversions...", "scale");
run("Size...", "width=800 height=800 constrain average interpolation=Bilinear");
//print(dir_argoloj+"homogeneite.jpg");
saveAs("Jpeg", dir_argoloj+"homogeneite.jpg");

}


macro 'Homogeneite Action Tool Options'  {
    Dialog.create("Homogeneite");
Dialog.addNumber("Taille du filtre:", radius_homogeneite);
Dialog.addChoice("Seuillage:", newArray("Manuel","Default","Huang","Intermodes","IsoData","IJ_IsoData","Li","MaxEntropy","Mean","MinError","Minimum","Moments","Otsu","Percentile","RenyiEntropy","Shanbhag","Triangle","Yen"),seuil_homogeneite[0]);
Dialog.addSlider("Surface de la croix mini", 1, 500, taille_homogeneite[0]);
Dialog.addSlider("Surface de la croix maxi", taille_homogeneite[0], 500, taille_homogeneite[1]);
Dialog.addCheckbox("Croix centrale a enlever", croix);
Dialog.addCheckbox("Valeurs par defaut", false);
Dialog.show();
radius_homogeneite=Dialog.getNumber();
seuil_homogeneite[0]=Dialog.getChoice();
taille_homogeneite[0]=Dialog.getNumber();
taille_homogeneite[1]=Dialog.getNumber();
croix=Dialog.getCheckbox();
raz_value=Dialog.getCheckbox();
if(raz_value){
    seuil_homogeneite=newArray("Otsu",100,255);
radius_homogeneite=1;
taille_homogeneite=newArray(20,100);
croix=false;
}
}
