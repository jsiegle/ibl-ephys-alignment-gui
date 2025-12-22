# IBL Ephys Alignment GUI

![GUI Screenshot](ephys_atlas_image.png)

GUI developed by the International Brain Laboratory for aligning electrophysiology data with histology data.

Usage instructions can be found on the [`iblapps` wiki](https://github.com/int-brain-lab/iblapps/wiki)


## Allen Institute for Neural Dynamics fork

This version of the GUI includes the following modifications:
- Only include code for the alignment app (and rename to `ephys_alignment_gui`)
- Restrict dependencies to `iblatlas`, `PyQt5`, and `pyqtgraph`
- Use separate directories for loading and saving, to allow input data to live in a read-only filesystem


## Installing

This version can be installed from GitHub via `pip`:

```
pip install git+https://github.com/AllenNeuralDynamics/ibl-ephys-alignment-gui.git
```

If you're running an Ubuntu workstation on Code Ocean, just add that line to the post-install script.

Once the package has been installed in your environment, you can run the GUI with the following command:

```
launch
```

# Expected Input File Structure

The GUI expects input data organized in the following structure:

```
<root>/
├── <subject_id>/
│   └── <subject_id>/
│       ├── ecephys_<subject_id>_<datetime>/      # Electrophysiology session
│       │   ├── <probe_id>/                        # One folder per probe (e.g., 46116-1, 45883-2)
│       │   │   ├── spikes.times.npy               # Spike timestamps
│       │   │   ├── spikes.amps.npy                # Spike amplitudes
│       │   │   ├── spikes.depths.npy              # Spike depths along probe
│       │   │   ├── spikes.clusters.npy            # Cluster IDs for each spike
│       │   │   ├── spike_shank_indices.npy        # Shank index for each spike
│       │   │   ├── clusters.channels.npy          # Channel per cluster
│       │   │   ├── clusters.peakToTrough.npy      # Peak-to-trough time
│       │   │   ├── clusters.waveforms.npy         # Mean waveforms
│       │   │   ├── clusters.metrics.csv           # Quality metrics
│       │   │   ├── unit_shank_indices.npy         # Shank index per unit
│       │   │   ├── channels.localCoordinates.npy  # XY coordinates on probe
│       │   │   ├── channels.rawInd.npy            # Raw channel indices
│       │   │   ├── _iblqc_ephysTimeRmsAP*.npy     # AP band RMS over time
│       │   │   ├── _iblqc_ephysTimeRmsLF*.npy     # LF band RMS over time
│       │   │   ├── _iblqc_ephysSpectralDensityAP*.npy  # AP power spectra
│       │   │   ├── _iblqc_ephysSpectralDensityLF*.npy  # LF power spectra
│       │   │   ├── xyz_picks.json                 # Track coordinates (CCF space)
│       │   │   └── xyz_picks_image_space.json     # Track coordinates (image space)
│       │   └── out/                               # [OUTPUT - ignored]
│       │
│       ├── ccf_space_histology/                   # Histology warped to CCF space
│       │   ├── histology_registration.nrrd        # Autofluorescence channel
│       │   └── histology_Ex_*_Em_*.nrrd           # Additional fluorescence channels
│       │
│       ├── image_space_histology/                 # Histology in original SPIM space
│       │   ├── histology_registration.nrrd        # Autofluorescence channel
│       │   ├── Ex_*_Em_*.nrrd                     # Additional fluorescence channels
│       │   ├── ccf_in_mouse.nrrd                  # CCF atlas warped to image space
│       │   └── labels_in_mouse.nrrd               # CCF labels warped to image space
│       │
│       └── track_data/                            # Probe track annotations
│           ├── ccf/                               # Tracks in CCF coordinates
│           │   └── <track_name>.fcsv              # Slicer fiducial format
│           ├── spim/                              # Tracks in SPIM coordinates
│           │   └── <track_name>.fcsv
│           ├── template/                          # Tracks in template coordinates
│           │   └── <track_name>.fcsv
│           └── bregma_xyz/                        # Tracks with bregma-relative coords
│               ├── <track_name>_ccf.json          # CCF coordinates
│               └── <track_name>_image_space.json  # Image space coordinates
│
├── SmartSPIM_<subject_id>/                        # SPIM registration transforms
│   └── image_atlas_alignment/
│       └── Ex_488_Em_525/
│           ├── ls_to_template_*GenericAffine.mat  # Affine transforms
│           ├── ls_to_template_*Warp.nii.gz        # Warp fields
│           └── moved_ls_to_ccf.nii.gz             # Registered image
│
├── allen_mouse_ccf_annotations_lateralized_compact/  # CCF atlas annotations
│   ├── ccf_2017_annotation_<res>_lateralized_compact.nrrd
│   └── ccf_2017_annotation_<res>_lateralized_unique_vals.npz
│
└── spim_template_to_ccf/                          # Template-to-CCF transforms
    ├── *GenericAffine.mat                         # Affine transforms
    ├── *Warp.nii.gz / *InverseWarp.nii.gz         # Forward/inverse warp fields
    └── template_in_ccf_*.nii.gz                   # Transformed template images
```
