from operator import itemgetter
import os
from java.lang.reflect import Array
from java.lang import String


from OMERO_toolbox import open_image_plus
from OMERO_toolbox import omero_connect
from OMERO_toolbox import get_image_properties
from OMERO_toolbox import add_images_key_values
from OMERO_toolbox import upload_image

from ij import IJ


def parse_log(string):
    info = IJ.getLog()
    parse_output = {}
    parsed_lines = [line for line in info.splitlines() if string in line]
    for line in parsed_lines:
        key, value = line.split(' = ')
        parse_output[key] = value

    return parse_output


# RAW image analysis
def channel_intensity_profiles(image_title):
    IJ.selectWindow(image_title)
    IJ.run("Channel Intensity Profiles", "angles=3 phases=5")

    IJ.selectWindow(image_title.rsplit('.', 1)[0] + '_CIP')
    cip_imp = IJ.getImage()

    statistics = {}
    statistics.update(parse_log('total intensity variation (%) = '))
    statistics.update(parse_log('estimated intensity decay (%) = '))
    statistics.update(parse_log('maximum intensity difference between angles (%) = '))
    statistics.update(parse_log('relative intensity fluctuations (%) = '))

    return [cip_imp], statistics


def fourier_projections(image_title):
    IJ.selectWindow(image_title)
    IJ.run("Fourier Projections", "angles=3 phases=5")

    IJ.selectWindow(image_title.rsplit('.', 1)[0] + '_FPJ')
    fpj_imp = IJ.getImage()

    return [fpj_imp]


def motion_illumination_variation(image_title):
    IJ.selectWindow(image_title)
    IJ.run("Motion & Illumination Variation", "angles=3 phases=5")

    IJ.selectWindow(image_title.rsplit('.', 1)[0] + '_MIV')
    miv_imp = IJ.getImage()

    return [miv_imp]


def modulation_contrast(raw_image_title, sir_image_title, do_map):
    IJ.selectWindow(raw_image_title)
    IJ.run("Modulation Contrast", "angles=3 phases=5 z_window_half-width=1")

    output_images = []
    if do_map:
        IJ.run("Modulation Contrast Map",
               "calculate_mcnr_from_raw_data=" +
               raw_image_title +
               " camera_bit_depth=16 or,_specify_mcnr_stack=" +
               raw_image_title.rsplit('.', 1)[0] +
               "_MCN reconstructed_data_stack=" +
               sir_image_title)
        IJ.selectWindow(sir_image_title.rsplit('.', 1)[0] + '_MCM')
        mcm_imp = IJ.getImage()
        output_images.append(mcm_imp)

    IJ.selectWindow(raw_image_title.rsplit('.', 1)[0] + '_MCN')
    mcn_imp = IJ.getImage()
    IJ.setMinAndMax(0, 255)
    IJ.run("8-bit")
    output_images.append(mcn_imp)

    statistics = {}
    statistics.update(parse_log('average feature MCNR = '))
    statistics.update(parse_log('estimated Wiener filter optimum = '))

    return output_images, statistics


# Reconstructed image analysis
def intensity_histogram(image_title):
    IJ.selectWindow(image_title)
    IJ.run("Intensity Histogram", " ")

    statistics = {}
    statistics.update(parse_log('max-to-min intensity ratio = '))

    return statistics


def fourier_plots(image_title):
    IJ.selectWindow(image_title)
    IJ.run("Fourier Plots", "applyWinFunc=True")

    IJ.selectWindow(image_title.rsplit('.', 1)[0] + '_FTL')
    ftl_imp = IJ.getImage()
    
    # IJ.run("To ROI Manager")
    # TODO: add ROIs to fourier plots

    IJ.selectWindow(image_title.rsplit('.', 1)[0] + '_FTR')
    # TODO: convert to RGB
    ftr_imp = IJ.getImage()

    return [ftl_imp, ftr_imp]


def main_function():
    # Clean up
    IJ.run("Close All")
    # TODO: condition closing or reseting log window to the fact that it is open
    # IJ.selectWindow("Log")
    # IJ.run("Close")

    # Connect to OMERO
    gateway = omero_connect(omero_server, omero_port, user_name, user_pw)

    # Get Images IDs and names
    images_dict = get_image_properties(gateway, dataset_id, group_id)

    images = [(images_dict[id]['name'], id) for id in images_dict]

    # Sort and get image names
    images.sort(key=itemgetter(0))
    
    # We are assuming here a standard OMX naming pattern for raw and sim images
    sim_images = [i[0] for i in images if i[0].endswith(sim_subfix)]
    raw_images = [i.rstrip(sim_subfix) + raw_subfix for i in sim_images]
    sim_images_ids = [i for i in images if i[0] in sim_images]
    raw_images_ids = [i for i in images if i[0] in raw_images]

    if len(sim_images_ids) != len(raw_images_ids):
        print("Some of the images do not have a raw-sim correspondance")
        gateway.disconnect()
        print("Script has been aborted")
        return

    # Iterate through the list of images to analyze
    for i in range(len(sim_images_ids)):
        raw_image_title = raw_images_ids[i][0]
        raw_image_id = raw_images_ids[i][1]
        sim_image_title = sim_images_ids[i][0]
        sim_image_id = sim_images_ids[i][1]

        print("Analyzing RAW image: " + raw_image_title + " with id: " + str(raw_image_id))
        print("Analyzing SIM image: " + sim_image_title + " with id: " + str(sim_image_id))

        #Reset raw_imp and sim_imp so we can test to see if we have downloaded
        # the relevant image later
        raw_imp = None
        sim_imp = None
        log_window = None
        raw_image_measurements = {}
        sim_image_measurements = {}
        output_images = []

        if (do_channel_intensity_profiles and
                 not ((raw_image_title.rsplit('.', 1)[0] + '_CIP.ome.tiff') in
                      map(lambda x: x[0], images))):
            
            if raw_imp is None :
                open_image_plus(omero_server,user_name,user_pw,
                                group_id,raw_image_id)
                IJ.selectWindow(raw_image_title)
                raw_imp = IJ.getImage()
            output, measurement = channel_intensity_profiles(raw_image_title)
            raw_image_measurements.update(measurement)
            log_window = True
            output_images += output

        if (do_fourier_projections and
            not ((raw_image_title.rsplit('.', 1)[0] + '_FPJ.ome.tiff') in
                      map(lambda x: x[0], images))):
            if raw_imp is None :
                open_image_plus(omero_server,user_name,user_pw,
                                group_id,raw_image_id)
                IJ.selectWindow(raw_image_title)
                raw_imp = IJ.getImage()
            output_images += fourier_projections(raw_image_title)

        if (do_motion_illumination_variation and
            not ((raw_image_title.rsplit('.', 1)[0] + '_MIV.ome.tiff') in
                      map(lambda x: x[0], images))):
            if raw_imp is None :
                open_image_plus(omero_server,user_name,user_pw,
                                group_id,raw_image_id)
                IJ.selectWindow(raw_image_title)
                raw_imp = IJ.getImage()
            output_images += motion_illumination_variation(raw_image_title)

        if ((do_modulation_contrast or do_modulation_contrast_map) and
            not ((raw_image_title.rsplit('.', 1)[0] + '_MCN.ome.tiff') in
                      map(lambda x: x[0], images))):
            if raw_imp is None :
                open_image_plus(omero_server,user_name,user_pw,
                                group_id,raw_image_id)
                IJ.selectWindow(raw_image_title)
                raw_imp = IJ.getImage()
            if sim_imp is None :
                open_image_plus(omero_server,user_name,
                                user_pw,group_id,sim_image_id)
                IJ.selectWindow(sim_image_title)
                sim_imp = IJ.getImage()
            output, measurement = modulation_contrast(raw_image_title,
                                                      sim_image_title,
                                                      do_modulation_contrast_map)
            raw_image_measurements.update(measurement)
            log_window = True
            output_images += output

        if do_intensity_histogram:
            if sim_imp is None :
                open_image_plus(omero_server,user_name,
                                user_pw,group_id,sim_image_id)
                IJ.selectWindow(sim_image_title)
                sim_imp = IJ.getImage()
            measurement = intensity_histogram(sim_image_title)
            log_window = True
            sim_image_measurements.update(measurement)

        if (do_fourier_plots and 
            not ((sim_image_title.rsplit('.', 1)[0] + '_FTL.ome.tiff') in
                      map(lambda x: x[0], images))):
            if sim_imp is None :
                open_image_plus(omero_server,user_name,
                                user_pw,group_id,sim_image_id)
                IJ.selectWindow(sim_image_title)
                sim_imp = IJ.getImage()
            output_images += fourier_plots(sim_image_title)

        if raw_image_measurements:
            add_images_key_values(gateway, raw_image_measurements, raw_image_id,
                              group_id, "SIMcheck")
        if sim_image_measurements:
            add_images_key_values(gateway, sim_image_measurements, sim_image_id,
                              group_id, "SIMcheck")

        for output_image in output_images:
        
            image_title = output_image.getTitle() + ".ome.tiff"
            image_path = os.path.join(str(temp_path), image_title)
            IJ.run(output_image, 'Bio-Formats Exporter', 'save=' + image_path + ' export compression=Uncompressed')
            output_image.changes = False
            output_image.close()
            # Upload image to OMERO
            print('Success: ' + str(upload_image(gateway, image_path, omero_server, dataset_id)))

        # Clean up close widnows that have been opened 
        if sim_imp or raw_imp:
            IJ.run("Close All")
        #close log window if it exists
        if log_window:
            IJ.selectWindow("Log")
            IJ.run("Close")

    print("Done")
    return gateway.disconnect()

# get OMERO credentials
#@string(label="Server", value="omero.mri.cnrs.fr", persist=true) omero_server
#@int(label="Port", value=4064, persist=true) omero_port
#@string(label="Username", persist=true) user_name
#@string(label="Password", persist=false) user_pw

# get the path for a temporary directory to store files
#@File(label="Select a temporary directory", style="directory") temp_path

# get Dataset id
#@int(label="Dataset ID") dataset_id
#@int(label="Group ID") group_id

#@string(value='.dv') raw_subfix
#@string(value='_SIR.dv') sim_subfix

#@boolean(label='Do channel intensity profiles', value=true, persist=true) do_channel_intensity_profiles
#@boolean(label='Do fourier projections', value=true, persist=true) do_fourier_projections
#@boolean(label='Do motion illumination variation', value=true, persist=true) do_motion_illumination_variation
#@boolean(label='Do modulation contrast', value=true, persist=true) do_modulation_contrast
#@boolean(label='Do modulation contrast map', value=true, persist=true) do_modulation_contrast_map
#@boolean(label='Do channel intensity histogram', value=true, persist=true) do_intensity_histogram
#@boolean(label='Do fourier plots', value=true, persist=true) do_fourier_plots


main_function()
