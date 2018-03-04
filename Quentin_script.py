'''Salut Julio,

Comme discuté hier, tu trouveras ci-dessous un macro que j’utilise pour compter des maximums locaux dans des objets segmentés sur des images de SIM.
Il n’y pas la segmentation de noyaux ici, comme je devais dans tous le cas noter à la main le nombre de maxima/noyau.

Tu peux l’essayer sur l’image que j’ai mis ici :

R:\Commun-ALL\Quentin_Julio
'''



run("Threshold and 16-bit Conversion", "  channel=0");
run("Z Project...", "projection=[Max Intensity]");

title=getTitle();
run("Split Channels");
C1Window="C1-"+title;
C2Window="C2-"+title;

selectWindow(C1Window);
run("Duplicate...", "duplicate");
setAutoThreshold("Otsu dark");
setOption("BlackBackground", true);
run("Convert to Mask");
run("Analyze Particles...", "size=6-Infinity pixel exclude add in_situ");


selectWindow(C1Window);
run("Enhance Contrast", "saturated=0.01");
run("Magenta Hot");

selectWindow(C2Window);
run("Enhance Contrast", "saturated=0.0001");
run("Grays");

run("Merge Channels...", "c1=["+C1Window+"] c2=["+C2Window+"] create")

selectWindow(title)
roiManager("Show All");
run("Find Maxima...", "noise=2500 output=[Point Selection]");
q