from operator import itemgetter
from os import path

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
    IJ.run("To ROI Manager")

    IJ.selectWindow(image_title.rsplit('.', 1)[0] + '_FTR')
    ftr_imp = IJ.getImage()

    return [ftl_imp, ftr_imp]


def main_function():

    # Connect to OMERO
    gateway = omero_connect(omero_server, omero_port, user_name, user_pw)

    # Get Images IDs and names
    images_dict = get_image_properties(gateway, dataset_id)

    images = [(name, images_dict[name]) for name in images_dict]

    # Sort and get image names
    images.sort(key=itemgetter(0))

    # We are assuming here a standard OMX naming pattern for raw and sim images
    sim_image_names = [i[0] for i in images if i[0].endswith(sim_subfix)]
    raw_image_names = [i.rstrip(sim_subfix) + raw_subfix  for i in sim_image_names]

    image_sets_to_analize = []

    for i in range(len(sim_image_names)):
        try:
            image_sets_to_analize.append((raw_image_names[i],
                                          images_dict[raw_image_names[i]],
                                          sim_image_names[i],
                                          images_dict[sim_image_names[i]]))
        except KeyError:
            print("Some of the images do not have a raw-sim correspondance")
            gateway.disconnect()
            print("Script has been aborted")
            return


    # Iterate through the list of images to analyze
    for image_set in image_sets_to_analize:

        raw_image_title = image_set[0]
        raw_image_id = image_set[1]
        sim_image_title = image_set[2]
        sim_image_id = image_set[3]

        print("Analyzing RAW image: " + raw_image_title)
        print("Analyzing SIM image: " + sim_image_title)

        # open the raw and sim images
        open_image_plus(omero_server,user_name,user_pw,group_id,raw_image_id)
        IJ.selectWindow(raw_image_title)
        raw_imp = IJ.getImage()
        open_image_plus(omero_server,user_name,user_pw,group_id,sim_image_id)
        IJ.selectWindow(sim_image_title)
        sim_imp = IJ.getImage()

        raw_image_measurements = {}
        sim_image_measurements = {}
        output_images = []
        if do_channel_intensity_profiles:
            output, measurement = channel_intensity_profiles(raw_image_title)
            raw_image_measurements.update(measurement)
            output_images += output

        if do_fourier_projections:
            output_images += fourier_projections(raw_image_title)

        if do_motion_illumination_variation:
            output_images += motion_illumination_variation(raw_image_title)

        if do_modulation_contrast or do_modulation_contrast_map:
            output, measurement = modulation_contrast(raw_image_title, sim_image_title, do_modulation_contrast_map)
            raw_image_measurements.update(measurement)
            output_images += output

        if do_intensity_histogram:
            measurement = intensity_histogram(sim_image_title)
            sim_image_measurements.update(measurement)

        if do_fourier_plots:
            output_images += fourier_plots(sim_image_title)

        add_images_key_values(gateway, raw_image_measurements, raw_image_id, "SIMcheck")
        add_images_key_values(gateway, sim_image_measurements, sim_image_id, "SIMcheck")

        for output_image in output_images:

            image_path = path.join(temp_path, (output_image.getTitle() + '.ome.tiff'))
            IJ.run(output_image, 'Bio-Formats Exporter', 'save=' + image_path + ' export compression=Uncompressed')
            output_image.changes = False
            output_image.close()
            # Upload image to OMERO
            str2d = java.lang.reflect.Array.newInstance(java.lang.String,[1])
            str2d [0] = image_path
            print('Importing image: ' + output_image.getTitle())
            success = upload_image(gateway, str2d, omero_server, dataset_id)
            print('Success: ' + str(success))

        # Clean up
        IJ.run("Close All")
        IJ.selectWindow("Log")
        IJ.run("Close")

    print("Done")
    return gateway.disconnect()

# get OMERO credentials
#@string(label="Server", value="omero.mri.cnrs.fr", persist=true) omero_server
#@int(label="Port", value="4064", persist=true) omero_port
#@string(label="Username", persist=true) user_name
#@string(label="Password", persist=false) user_pw

# get teh path for a temporary directory to store files
#@File(label="Select a temporary directory", style="directory") temp_path

# get Dataset id
#@int(label="Dataset ID") dataset_id
#@int(label="Group ID") group_id

#@string(value='.dv') raw_subfix
#@string(value='_SIR.dv') sim_subfix

#@boolean(label='Do channel intensity profiles', value=true) do_channel_intensity_profiles
#@boolean(label='Do fourier projections', value=true) do_fourier_projections
#@boolean(label='Do motion illumination variation', value=true) do_motion_illumination_variation
#@boolean(label='Do modulation contrast', value=true) do_modulation_contrast
#@boolean(label='Do modulation contrast map', value=true) do_modulation_contrast_map
#@boolean(label='Do channel intensity histogram', value=true) do_intensity_histogram
#@boolean(label='Do fourier plots', value=true) do_fourier_plots


main_function()