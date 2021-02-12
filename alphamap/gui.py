#!python

# external
import os
import re
import sys
import numpy as np
import pandas as pd
from io import StringIO
import pyteomics.fasta
# visualization libraries
import panel as pn
import plotly.graph_objects as go
# local
from alphamap.importing import import_data
from alphamap.preprocessing import format_input_data
from alphamap.sequenceplot import plot_peptide_traces
from alphamap.uniprot_integration import uniprot_feature_dict
from alphamap.sequenceplot import uniprot_color_dict
from alphamap.proteolytic_cleavage import protease_dict
from alphamap.organisms_data import all_organisms


# EXTENSIONS
css = '''
.bk-root .bk-btn-default.bk-active {
    background-color: #AECCE6;
}

.bk.accordion {
    font-size: smaller;
}

.bk-root .bk-btn {
    padding: 6px 0px 6px 0px;
}

.bk.uniprot_options {
    margin: 17px 6px 12px 6px;
    background-color: white;
    font-size: 13px;
    font-weight: initial;
    text-align: center;
    height: 55px;
    border: 1px solid #e0e0e0;
    border-radius: 2px;
}

.bk-root .bk-btn-primary {
    background-color:  ;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.5px;
}

.bk-root .bk-btn-default {
    color: dimgrey;
    font-size: 11px;
    font-weight: 700;
}

.bk.card-title {
    font-size: 13px;
    font-weight: initial;
}

h1 {
    color: #045082;
    font-size: 45px;
    line-height: 0.6;
    text-align: center;
}

h4 {
    color: #173245;
    font-size: 18px;
    line-height: 0.6;
    text-align: center;
}

.codehilite {
    color: #173245;
    font-size: 14px;
    background-color: #eaeaea;
}

.codehilite .s1 {
    color: #173245;
    font-weight: initial;
}

.codehilite .s2 {
    color: #173245;
    font-weight: bold;
}

.codehilite .ow {
    color: #173245;
    font-weight: initial;
}

.codehilite .k {
    color: #173245;
    font-weight: initial;
}

.bk.opt {
    position: relative;
    display: block;
    left: 75px;
    top: 0px;
    width: 80px;
    height: 80px;
}

.bk.main-part {
    background-color: #EAEAEA;
    font-size: 17px;
    line-height: 23px;
    letter-spacing: 0px;
    font-weight: 500;
    color: #045082;
    text-align: center;
    position: relative !important;
    margin-left: auto;
    margin-right: auto;
    width: 40%;
}

.bk.selection_box {
    background-color: #EAEAEA;
}

.bk.alert-danger {
    background-color: #EAEAEA;
    color: #c72d3b;
    border: 0px #EAEAEA solid;
    padding: 0;
    font-size: 12px;
}

.bk.alert-info {
    background-color: #EAEAEA;
    border: 0px #EAEAEA solid;
    padding: 0;
    font-size: 12px;
}

'''
pn.extension(raw_css=[css])
pn.extension('plotly')


# LOCAL VARIABLES
full_fasta = None
full_uniprot = None
ac_gene_conversion = None
SETTINGS = {
    'max_file_size_gb':20
}
SERVER = None

# ERROR/WARNING MESSAGES
error_message_upload = "The selected file can't be uploaded. Please check the instructions for data uploading."
error_message_size = f"A maximum file size shouldn't exceed {SETTINGS['max_file_size_gb']} GB."

### PATHS
BASE_PATH = os.path.dirname(__file__)
DATA_PATH = os.path.join(BASE_PATH, "data")
IMAGE_PATH = os.path.join(BASE_PATH, "data", "img")

mpi_biochem_logo_path = os.path.join(IMAGE_PATH, "mpi_logo.png")
mpi_logo_path = os.path.join(IMAGE_PATH, "max-planck-gesellschaft.jpg")
github_logo_path = os.path.join(IMAGE_PATH, "github.png")

alphamap_tutorial_path = os.path.join(DATA_PATH, "alphamap_tutorial.pdf")
spectronaut_scheme_path = os.path.join(DATA_PATH, "spectronaut_export_scheme.rs")

uniprot_link_path = os.path.join(IMAGE_PATH, "uniprot_logo.png")
phosposite_link_path = os.path.join(IMAGE_PATH, "phosphosite_logo.png")
protter_link_path = os.path.join(IMAGE_PATH, "protter_logo.png")
pdb_link_path = os.path.join(IMAGE_PATH, "pdb_logo.png")


### HEADER
header_titel = pn.pane.Markdown(
    '# AlphaMap',
    width=1250,
    css_classes=['main_header']
)
divider = pn.pane.HTML(
    '<hr style="height: 2px; border:none; background-color: #045082; width: 1480px">',
    width=1500,
    align='center'
)
mpi_biochem_logo = pn.pane.PNG(
    mpi_biochem_logo_path,
    link_url='https://www.biochem.mpg.de/mann',
    width=60,
    height=60,
    align='start'
)
mpi_logo = pn.pane.JPG(
    mpi_logo_path,
    link_url='https://www.biochem.mpg.de/en',
    height=62,
    embed=True,
    width=62,
    margin=(5, 0, 0, 5),
    css_classes=['opt']
)
github_logo = pn.pane.PNG(
    github_logo_path,
    link_url='https://github.com/MannLabs/pepmap',
    height=70,
)
header = pn.Row(
    mpi_biochem_logo,
    mpi_logo,
    header_titel,
    github_logo,
    height=70
)


### WIDGETS

#####################################
# SELECTORS
select_protein = pn.widgets.AutocompleteInput(
    name='Select a protein of interest:',
    placeholder='Type first letters ...',
    min_characters=1,
    case_sensitive=False
)
predefined_protein_list_titel = pn.pane.Markdown(
    'Load a list of pre-selected proteins:',
    margin=(0,0,0,12)
)
predefined_protein_list = pn.widgets.FileInput(
    accept=".txt",
    margin=(-10,0,5,12)
)
select_organism = pn.widgets.Select(
    name='Select an organism:',
    value='Human',
    options=['Human', 'Mouse', 'Rat', 'Cow', 'Zebrafish', 'Drosophila', 'Caenorhabditis elegans', 'Slime mold',
             'Arabidopsis thaliana', 'Rice', 'Escherichia coli', 'Bacillus subtilis', 'Saccharomyces cerevisiae'],
    align='center',
    margin=(0,0,0,7),
    width=300
)

#####################################
# RADIOBUTTONS/CHECKBOXES
search_by = pn.widgets.RadioBoxGroup(
    name='Search by',
    options=['Search by UniProt accession', 'Search by a gene name'],
    value='Search by UniProt accession'
)
select_all = pn.widgets.Checkbox(
    name='Select all',
    width=150
)
clear_all = pn.widgets.Checkbox(
    name='Clear all',
    width=150
)
proteases_select_all = pn.widgets.Checkbox(
    name='Select all',
    width=150
)
proteases_clear_all = pn.widgets.Checkbox(
    name='Clear all',
    width=150
)

#####################################
# RAW EXPERIMENTAL DATA

# first experimental file
experimental_data = pn.widgets.TextInput(
    name='Upload a result file:',
    placeholder='D:\spectronaut_output.csv',
    width=445,
    margin=(23,0,5,15)
)
experimental_data_loading_spinner = pn.indicators.LoadingSpinner(
    value=False,
    bgcolor='light',
    color='secondary',
    margin=(43,0,3,12),
    width=30,
    height=30
)
experimental_data_sample = pn.widgets.MultiSelect(
    name='Select samples:',
    disabled=True,
    size=5,
    width=770,
    margin=(0,0,20,14)
)
experimental_data_warning = pn.pane.Alert(
    width=550,
    height=30,
    alert_type="danger",
    margin=(-20,0,15,15)
)
experimental_data_sample_name = pn.widgets.TextInput(
    name='Sample name',
    disabled=True,
    width=130,
    margin=(23,0,5,11)
)
experimental_data_sample_name_remove_part = pn.widgets.TextInput(
    name='Prefix / suffix',
    disabled=True,
    width=130,
    margin=(23,0,5,10)
)
# second experimental file
experimental_data_2 = pn.widgets.TextInput(
    name='Upload a result file:',
    placeholder='D:\spectronaut_output.csv',
    width=445,
    margin=(23,0,5,15)
)
experimental_data_2_loading_spinner = pn.indicators.LoadingSpinner(
    value=False,
    bgcolor='light',
    color='secondary',
    margin=(43,0,3,12),
    width=30,
    height=30
)
experimental_data_2_sample = pn.widgets.MultiSelect(
    name='Select samples:',
    size=5,
    disabled=True,
    width=770,
    margin=(0,0,0,14)
)
experimental_data_2_warning = pn.pane.Alert(
    width=550,
    height=30,
    alert_type="danger",
    margin=(-20,0,15,15)
)
experimental_data_2_sample_name = pn.widgets.TextInput(
    name='Sample name',
    disabled=True,
    width=130,
    margin=(23,0,5,11)
)
experimental_data_2_sample_name_remove_part = pn.widgets.TextInput(
    name='Prefix / suffix',
    disabled=True,
    width=130,
    margin=(23,0,5,10)
)
# third experimental file
experimental_data_3 = pn.widgets.TextInput(
    name='Upload a result file:',
    placeholder='D:\spectronaut_output.csv',
    width=445,
    margin=(23,0,5,15)
)
experimental_data_3_loading_spinner = pn.indicators.LoadingSpinner(
    value=False,
    bgcolor='light',
    color='secondary',
    margin=(43,0,3,12),
    width=30,
    height=30
)
experimental_data_3_sample = pn.widgets.MultiSelect(
    name='Select samples:',
    size=5,
    disabled=True,
    width=770,
    margin=(0,0,20,14)
)
experimental_data_3_warning = pn.pane.Alert(
    width=550,
    height=30,
    alert_type="danger",
    margin=(-20,0,15,15)
)
experimental_data_3_sample_name = pn.widgets.TextInput(
    name='Sample name',
    disabled=True,
    width=130,
    margin=(23,0,5,11)
)
experimental_data_3_sample_name_remove_part = pn.widgets.TextInput(
    name='Prefix / suffix',
    disabled=True,
    width=130,
    margin=(23,0,5,10)
)
#####################################
# PREPROCESSED EXPERIMENTAL DATA
preprocessed_exp_data = pn.widgets.DataFrame(
    name='Exp_data'
)
preprocessed_exp_data_2 = pn.widgets.DataFrame(
    name='Exp_data_2'
)
preprocessed_exp_data_3 = pn.widgets.DataFrame(
    name='Exp_data_3'
)

#####################################
# BUTTONS
upload_button = pn.widgets.Button(
    name='Upload data',
    button_type='primary',
    css_classes=['button_options'],
    height=40,
    width=170,
    margin=(0,0,0,638)
)
upload_spinner = pn.indicators.LoadingSpinner(
    value=False,
    bgcolor='light',
    color='secondary',
    margin=(0,0,20,10),
    width=40,
    height=40
)
exit_button = pn.widgets.Button(
    name='QUIT',
    button_type='default',
    css_classes=['button_options'],
    height=40,
    width=170,
    margin=(0,0,0,430)
)
visualize_button = pn.widgets.Button(
    name='Visualize protein',
    button_type='primary',
    css_classes=['button_options'],
    height=40,
    width=170,
    align='center',
    margin=(0,0,0,0)
)
visualize_spinner = pn.indicators.LoadingSpinner(
    value=False,
    bgcolor='light',
    color='secondary',
    align='center',
    margin=(0,0,20,20),
    width=40,
    height=40
)


### UNIPROT OPTIONS
options_preprocessing_events = pn.widgets.CheckButtonGroup(
    name='Molecule processing',
    value=['Chain', 'Initiator methionine', 'Peptide', 'Propeptide', 'Signal peptide', 'Transit peptide'],
    options=['Chain', 'Initiator methionine', 'Peptide', 'Propeptide', 'Signal peptide', 'Transit peptide'],
    align='center'
)
options_PTMs = pn.widgets.CheckButtonGroup(
    name='Post-translational modification',
    options=['Cross-link', 'Disulfide bond', 'Glycosylation', 'Lipidation', 'Modified residue'],
    value=['Cross-link', 'Disulfide bond', 'Glycosylation', 'Lipidation', 'Modified residue'],
    align='center'
)
options_domains = pn.widgets.CheckButtonGroup(
    name='Family & Domain',
    options=['Coiled coil', 'Compositional bias', 'Domain', 'Motif', 'Region', 'Repeat', 'Zinc finger'],
    value=['Coiled coil', 'Compositional bias', 'Domain', 'Motif', 'Region', 'Repeat', 'Zinc finger'],
    align='center'
)
options_locations = pn.widgets.CheckButtonGroup(
    name='Subcellular location',
    options=['Intramembrane', 'Topological domain', 'Transmembrane'],
    value=['Intramembrane', 'Topological domain', 'Transmembrane'],
    align='center'
)
options_functions = pn.widgets.CheckButtonGroup(
    name='Function',
    options=['Active site', 'Binding site', 'Calcium binding', 'DNA binding', 'Metal binding', 'Nucleotide binding', 'Site'],
    value=['Active site', 'Binding site', 'Calcium binding', 'DNA binding', 'Metal binding', 'Nucleotide binding', 'Site'],
    align='center'
)
options_sequences = pn.widgets.CheckButtonGroup(
    name='Sequence',
    options=['Alternative sequence', 'Natural variant', 'Non-adjacent residues', 'Non-standard residue',
             'Non-terminal residue', 'Sequence conflict', 'Sequence uncertainty'],
    value=['Alternative sequence', 'Natural variant', 'Non-adjacent residues', 'Non-standard residue',
             'Non-terminal residue', 'Sequence conflict', 'Sequence uncertainty'],
    align='center'
)
options_other = pn.widgets.CheckButtonGroup(
    name='Other options',
    options=['Secondary structure', 'Mutagenesis'],
    value=['Secondary structure', 'Mutagenesis'],
    align='center'
)

#####################################
### LAYOUTS
uniprot_options = pn.Accordion(
    options_preprocessing_events,
    options_PTMs,
    options_domains,
    options_locations,
    options_functions,
    options_sequences,
    options_other,
    active=list(range(0,7)),
    header_background='EAEAEA',
    active_header_background='EAEAEA',
    width = 850
)

uniprot_options_tab = pn.Card(
    uniprot_options,
    pn.Row(
        select_all,
        clear_all,
        margin=5
    ),
    title='UniProt annotations',
    collapsed=True,
    header_background='EAEAEA',
    active_header_background='EAEAEA',
    width=860,
    css_classes=['uniprot_options'],
)


### List of proteases
proteases_options = pn.widgets.CheckBoxGroup(
    options=list(protease_dict.keys()),
    value=['trypsin'],
    align='center',
    margin=10
)

proteases_options_tab = pn.Card(
    proteases_options,
    pn.Row(
        proteases_select_all,
        proteases_clear_all,
        margin=5
    ),
    title='Protease cleavage sites',
    collapsed=True,
    header_background='EAEAEA',
    active_header_background='EAEAEA',
    width=860,
    css_classes=['uniprot_options'],
)


### MAIN PART
project_description = pn.pane.Markdown(
    """### This website enables the exploration of proteomic datasets on the peptide level. It is possible to evaluate the sequence coverage of any identified protein and its post-translational modifications (PTMs). AlphaMap further integrates all available UniProt sequence annotations as well as information about proteolytic cleavage sites.""",
    margin=(10, 0, -20, 0),
    css_classes=['main-part'],
    width=635
)

divider_descr = pn.pane.HTML(
    '<hr style="height: 8px; border:none; background-color: #045082; width: 640px">',
    width=1510,
    align='center'
)

project_instuction = pn.pane.Markdown(
    """#### How to use AlphaMap:
    1. Select the organism of your proteomic study.
    2. Provide the filepath to your proteomic datasets analyzed by
    AlphaPept, MaxQuant or Spectronaut.
        - Wait for samples to be displayed in the 'Select samples' field.
        - (optional) Select either all samples (default) or any specific
        sample(s) to visualize together as one trace.
        - (optional) Choose a name by which the selected sample(s) will
        be displayed in the figure.
        - (optional) Provide a prefix or suffix to be removed from the
        original names of the selected samples.
        * Up to three datasets or sets of selected samples can be
        visualized together.
    3. Press the 'Upload Data' button.
    4. Select a protein of interest by UniProt accession or gene name.
    5. (optional) Load a list of pre-selected proteins to reduce the list
    of available proteins.
    6. Select annotation options for the sequence visualization.
    7. Press the 'Visualize Protein' button.
    8. Enjoy exploring your data!
    """,
    width=530,
    align='start',
    margin=(20, 80, 0, 10)
)

alphamap_tutorial = pn.widgets.FileDownload(
    file=alphamap_tutorial_path,
    filename='AlphaMap tutorial',
    button_type='default',
    auto=True,
    width=530,
    align='start',
    margin=(10, 80, 5, 10),
    css_classes=['spectronaut_instr']

)

spectronaut_description = pn.pane.Markdown(
    """
    The data needs to be exported in the **normal long** format as .tsv or .csv file.

    It needs to include the following columns:
    >- PEP.AllOccurringProteinAccessions
    >- EG.ModifiedSequence
    >- R.FileName

    To ensure the correct export format from Spectronaut, you can download and apply the provided export scheme “spectronaut_export_scheme.rs”.
    """,
    width=530,
    align='start',
    margin=(0, 80, 0, 20)
)

spectronaut_scheme = pn.widgets.FileDownload(
    file=spectronaut_scheme_path,
    filename='spectronaut_export_scheme.rs',
    button_type='default',
    auto=True,
    css_classes=['button_options'],
)

maxquant_description = pn.pane.Markdown(
    """
    To visualize the proteins which were analyzed by the MaxQuant software please use the **evidence.txt** file.

    The following columns from the file are used for visualization:
    >- Proteins
    >- Modified sequence
    >- Raw file
    """,
    width=530,
    align='start',
    margin=(0, 80, 0, 20)
)

spectronaut_instructions = pn.Card(
    spectronaut_description,
    spectronaut_scheme,
    title='Spectronaut instructions',
    collapsed=True,
    width=530,
    align='start',
    margin=(0, 80, 5, 10),
    css_classes=['spectronaut_instr']
)

maxquant_instructions = pn.Card(
    maxquant_description,
    title='MaxQuant instructions',
    collapsed=True,
    width=530,
    align='start',
    margin=(0, 80, 5, 10),
    css_classes=['spectronaut_instr']
)

additional_data_card = pn.Card(
    pn.Row(
        experimental_data_2,
        experimental_data_2_loading_spinner,
        experimental_data_2_sample_name,
        experimental_data_2_sample_name_remove_part
    ),
    experimental_data_2_warning,
    experimental_data_2_sample,
    pn.Row(
        experimental_data_3,
        experimental_data_3_loading_spinner,
        experimental_data_3_sample_name,
        experimental_data_3_sample_name_remove_part
    ),
    experimental_data_3_warning,
    experimental_data_3_sample,
    title='Upload additional result files',
    collapsed=True,
    width=780,
    margin=(2,0,0,10),
    css_classes=['add_experim_options']
)

selection_box = pn.Column(
    select_organism,
    pn.Row(
        experimental_data,
        experimental_data_loading_spinner,
        experimental_data_sample_name,
        experimental_data_sample_name_remove_part
    ),
    experimental_data_warning,
    experimental_data_sample,
    additional_data_card,
    margin=(20, 30, 10, 30),
    width=790,
    css_classes=['selection_box'],
)


main_part = pn.Column(
    project_description,
    divider_descr,
    pn.Row(
        pn.Column(
            project_instuction,
            alphamap_tutorial,
            spectronaut_instructions,
            maxquant_instructions
        ),
        selection_box,
        align='center'
    ),
    pn.Row(
        upload_button,
        upload_spinner,
        exit_button,
    ),
    background='#eaeaea',
    width=1510,
    margin=(5, 0, 10, 0)
)


# switch to different websites
uniprot_link = pn.pane.PNG(
    uniprot_link_path,
    width=120,
    height=60,
    align='start',
    margin=(0, 30, 0, 40)
)
phosposite_link = pn.pane.PNG(
    phosposite_link_path,
    width=200,
    height=60,
    align='start',
    margin=(0, 20)
)
protter_link = pn.pane.PNG(
    protter_link_path,
    width=140,
    height=60,
    align='start',
    margin=(0, 20)
)
pdb_link = pn.pane.PNG(
    pdb_link_path,
    width=120,
    height=60,
    align='start',
    margin=(0, 20)
)


def extract_uniprot_ai(protein, search_by):
    if search_by == 'Search by a gene name':
        return re.findall(r"\((?P<id>.+?)\)", protein)[0]
    return protein


def update_all_links():
    selected_protein_id = extract_uniprot_ai(select_protein.value, search_by.value)
    uniprot_link.link_url = 'https://www.uniprot.org/uniprot/' + selected_protein_id
    phosposite_link.link_url = 'http://www.phosphosite.org/uniprotAccAction?id=' + selected_protein_id
    protter_link.link_url = 'https://wlab.ethz.ch/protter/#up=' + selected_protein_id
    pdb_link.link_url = f'https://www.rcsb.org/search?request=%7B%22query%22%3A%7B%22parameters%22%3A%7B%22value%22%3A%22{selected_protein_id}%22%7D%2C%22type%22%3A%22terminal%22%2C%22service%22%3A%22text%22%2C%22node_id%22%3A0%7D%2C%22return_type%22%3A%22entry%22%2C%22request_options%22%3A%7B%22pager%22%3A%7B%22start%22%3A0%2C%22rows%22%3A100%7D%2C%22scoring_strategy%22%3A%22combined%22%2C%22sort%22%3A%5B%7B%22sort_by%22%3A%22score%22%2C%22direction%22%3A%22desc%22%7D%5D%7D%2C%22request_info%22%3A%7B%22src%22%3A%22ui%22%2C%22query_id%22%3A%223407f72e3370cd10196490437be3ec87%22%7D%7D'


@pn.depends(visualize_button.param.clicks)
def visualize_buttons(_):
    if select_protein.value:
        update_all_links()
        buttons_layout = pn.Row(
            pn.pane.Markdown(
                "### Inspect target protein on other platforms:",
                margin=(2, 0, 0, 0)
            ),
            uniprot_link,
            phosposite_link,
            protter_link,
            pdb_link,
            height=60,
            margin=(50, 0, 50, 80)
        )
        return buttons_layout
    else:
        return None


### PREPROCESSING
def upload_experimental_data():
    global ac_gene_conversion
    if experimental_data_sample.value == ['All samples']:
        data_samples = None
    else:
        data_samples = experimental_data_sample.value
    preprocessed_exp_data.value = format_input_data(
        df = import_data(
            experimental_data.value,
            verbose=False,
            sample=data_samples
        ),
        fasta = full_fasta,
        modification_exp = r'\[.*?\]',
        verbose = False)
    all_unique_proteins = preprocessed_exp_data.value.unique_protein_id.unique().tolist()
    if experimental_data_2.value:
        if experimental_data_2_sample.value == ['All samples']:
            data_2_samples = None
        else:
            data_2_samples = experimental_data_2_sample.value
        try:
            preprocessed_exp_data_2.value = format_input_data(
                df = import_data(
                    experimental_data_2.value,
                    verbose=False,
                    sample=data_2_samples
                ),
                fasta = full_fasta,
                modification_exp = r'\[.*?\]',
                verbose = False)
            all_unique_proteins.extend(preprocessed_exp_data_2.value.unique_protein_id.unique().tolist())
        except (TypeError, AttributeError) as e:
            pass
    if experimental_data_3.value:
        if experimental_data_3_sample.value == ['All samples']:
            data_3_samples = None
        else:
            data_3_samples = experimental_data_3_sample.value
        try:
            preprocessed_exp_data_3.value = format_input_data(
                df = import_data(
                    experimental_data_3.value,
                    verbose=False,
                    sample=data_3_samples
                ),
                fasta = full_fasta,
                modification_exp = r'\[.*?\]',
                verbose = False)
            all_unique_proteins.extend(preprocessed_exp_data_3.value.unique_protein_id.unique().tolist())
        except (TypeError, AttributeError):
            pass
    ac_gene_conversion = {
        each: f"{full_fasta.get_by_id(each).description.get('GN')} ({full_fasta.get_by_id(each).description.get('id')})" \
        for each in sorted(list(set(all_unique_proteins)))}
    # to set a selection list of availible proteins depending which user wants to search by
    if search_by.value == 'Search by a gene name':
        select_protein.options = list(ac_gene_conversion.values())
    else:
        select_protein.options = list(ac_gene_conversion.keys())


@pn.depends(
    predefined_protein_list.param.value,
    watch=True
)
def filter_proteins(data):
    global ac_gene_conversion
    predefined_list = StringIO(str(data, "utf-8")).readline().replace(' ', '').split(';')
    predefined_list = [protein.upper() for protein in predefined_list]
    ac_gene_conversion = {k:v for k,v in ac_gene_conversion.items() if (k in predefined_list or v.split()[0] in predefined_list)}
    if search_by.value == 'Search by a gene name':
        select_protein.options = list(ac_gene_conversion.values())
    else:
        select_protein.options = list(ac_gene_conversion.keys())


def upload_organism_info():
    global full_fasta, full_uniprot
    fasta_name = all_organisms[select_organism.value]['fasta_name']
    uniprot_name = all_organisms[select_organism.value]['uniprot_name']
    full_fasta = pyteomics.fasta.IndexedUniProt(os.path.join(DATA_PATH, fasta_name))
    full_uniprot = pd.read_csv(os.path.join(DATA_PATH, uniprot_name))


def extract_samples(path):
    """
    Extract information about unique sample names that present in the raw file analyzed by MaxQuant or Spectronaut.
    """
    sample_columns = ['R.FileName', 'Raw file']
    file_size_gb = os.stat(path).st_size / 1024**3
    if file_size_gb > SETTINGS['max_file_size_gb']:
        raise MemoryError
    try:
        unique_samples = pd.read_csv(path, sep=None, engine='python',
            usecols=lambda col: col in sample_columns).iloc[:, 0].unique().tolist()
    except:
        raise TypeError("This file can't be uploaded.")
    return unique_samples


def extract_name(filename, sample, sample_name, sample_name_remove_prefix):
    if sample_name:
        name = sample_name
    elif sample and sample != ['All samples']:
        if isinstance(sample, list):
            name = ";".join(sample).replace(sample_name_remove_prefix, '')
        else:
            name = sample.replace(sample_name_remove_prefix, '')
    else:
        name = filename.split('.')[0]
    return name


@pn.depends(
    experimental_data_sample_name.param.value,
    experimental_data_2_sample_name.param.value,
    experimental_data_3_sample_name.param.value,
    experimental_data_sample_name_remove_part.param.value,
    experimental_data_2_sample_name_remove_part.param.value,
    experimental_data_3_sample_name_remove_part.param.value,
    experimental_data_sample.param.value,
    experimental_data_2_sample.param.value,
    experimental_data_3_sample.param.value,
    experimental_data.param.value,
    experimental_data_2.param.value,
    experimental_data_3.param.value,
    select_organism.param.value,
    watch=True
)
def clear_dashboard(*args):
    upload_button.clicks = 0
    visualize_button.clicks = 0
    upload_data
    visualize_plot


@pn.depends(
    experimental_data.param.value,
    watch=True
)
def update_data_sample_info(data1):
    experimental_data_loading_spinner.value = True
    experimental_data_sample.disabled = False
    try:
        experimental_data_warning.object = None
        experimental_data_sample.options = ['All samples'] + extract_samples(data1)
        experimental_data_sample.value = ['All samples']
        experimental_data_sample_name_remove_part.disabled = False
    except (TypeError, MemoryError, FileNotFoundError) as e:
        if type(e).__name__ == 'MemoryError':
            experimental_data_warning.object = error_message_size
        elif type(e).__name__ == 'TypeError':
            experimental_data_warning.object = error_message_upload
        experimental_data_sample.disabled = True
        experimental_data_sample_name.disabled = True
        experimental_data_sample_name.value = ''
        experimental_data_sample_name_remove_part.disabled = True
        experimental_data_sample_name_remove_part.value = ''
        experimental_data_sample.options = []
        experimental_data_sample.value = []
    experimental_data_loading_spinner.value = False


@pn.depends(
    experimental_data_2.param.value,
    watch=True
)
def update_data_2_sample_info(data2):
    experimental_data_2_loading_spinner.value = True
    experimental_data_2_sample.disabled = False
    try:
        experimental_data_2_warning.object = None
        experimental_data_2_sample.options = ['All samples'] + extract_samples(data2)
        experimental_data_2_sample.value = ['All samples']
        experimental_data_2_sample_name_remove_part.disabled = False
    except (TypeError, MemoryError) as e:
        if type(e).__name__ == 'MemoryError':
            experimental_data_2_warning.object = error_message_size
        elif type(e).__name__ == 'TypeError':
            experimental_data_2_warning.object = error_message_upload
        experimental_data_2_sample.disabled = True
        experimental_data_2_sample_name.disabled = True
        experimental_data_2_sample_name.value = ''
        experimental_data_2_sample_name_remove_part.disabled = True
        experimental_data_2_sample_name_remove_part.value = ''
        experimental_data_2_sample.options = []
        experimental_data_2_sample.value = []
    experimental_data_2_loading_spinner.value = False


@pn.depends(
    experimental_data_3.param.value,
    watch=True
)
def update_data_3_sample_info(data3):
    experimental_data_3_loading_spinner.value = True
    experimental_data_3_sample.disabled = False
    try:
        experimental_data_3_warning.object = None
        experimental_data_3_sample.options = ['All samples'] + extract_samples(data3)
        experimental_data_3_sample.value = ['All samples']
        experimental_data_3_sample_name_remove_part.disabled = False
    except (TypeError, MemoryError) as e:
        if type(e).__name__ == 'MemoryError':
            experimental_data_3_warning.object = error_message_size
        elif type(e).__name__ == 'TypeError':
            experimental_data_3_warning.object = error_message_upload
        experimental_data_3_sample.disabled = True
        experimental_data_3_sample_name.disabled = True
        experimental_data_3_sample_name.value = ''
        experimental_data_3_sample_name_remove_part.disabled = True
        experimental_data_3_sample_name_remove_part.value = ''
        experimental_data_3_sample.options = []
        experimental_data_3_sample.value = []
    experimental_data_3_loading_spinner.value = False


@pn.depends(
    experimental_data_sample.param.value,
    experimental_data_2_sample.param.value,
    experimental_data_3_sample.param.value,
    watch=True
)
def change_sample_name_state(data_sample, data_2_sample, data_3_sample):
    if data_sample:
        experimental_data_sample_name.disabled = False
        experimental_data_sample_name_remove_part.disabled = False
    else:
        experimental_data_sample_name.disabled = True
        experimental_data_sample_name_remove_part.disabled = True
    if data_2_sample:
        experimental_data_2_sample_name.disabled = False
        experimental_data_2_sample_name_remove_part.disabled = False
    else:
        experimental_data_2_sample_name.disabled = True
        experimental_data_2_sample_name_remove_part.disabled = True
    if data_3_sample:
        experimental_data_3_sample_name.disabled = False
        experimental_data_3_sample_name_remove_part.disabled = False
    else:
        experimental_data_3_sample_name.disabled = True
        experimental_data_3_sample_name_remove_part.disabled = True


@pn.depends(
    select_all.param.value,
    clear_all.param.value,
    watch=True
)
def change_uniprot_selection(select, clear):
    if select:
        clear_all.value = False
        select_all.value = False
        for each in uniprot_options.objects:
            each.value = each.options
    if clear:
        clear_all.value = False
        select_all.value = False
        for each in uniprot_options.objects:
            each.value = []


@pn.depends(
    proteases_select_all.param.value,
    proteases_clear_all.param.value,
    watch=True
)
def change_proteases_selection(select, clear):
    if select:
        proteases_clear_all.value = False
        proteases_select_all.value = False
        proteases_options.value = proteases_options.options
    if clear:
        proteases_clear_all.value = False
        proteases_select_all.value = False
        proteases_options.value = []


@pn.depends(
    search_by.param.value,
    watch=True
)
def change_autocomplete_input(search_by):
    if any(
        [experimental_data_sample.value, experimental_data_2_sample.value, experimental_data_3_sample.value]
    ):
        if search_by == 'Search by a gene name':
            select_protein.options = list(ac_gene_conversion.values())
        else:
            select_protein.options = list(ac_gene_conversion.keys())


### VISUALIZATION
@pn.depends(
    upload_button.param.clicks
)
def upload_data(clicks):
    if clicks > 0 and any(
        [experimental_data_sample.value, experimental_data_2_sample.value, experimental_data_3_sample.value]
    ):
        upload_spinner.value = True
        select_protein.value = None
        # preload the data
        upload_organism_info()
        upload_experimental_data()
        # create a layout
        app = pn.Column(
            pn.Row(
                pn.layout.VSpacer(width=100),
                pn.Column(
                    select_protein,
                    search_by,
                    predefined_protein_list_titel,
                    predefined_protein_list
                ),
                pn.layout.VSpacer(width=80),
                pn.Column(
                    uniprot_options_tab,
                    proteases_options_tab
                ),
                align='center'
            ),
            pn.layout.HSpacer(height=4),
            pn.Row(
                visualize_button,
                visualize_spinner,
                align='center'
            ),
            divider,
            margin=(20, 0)
        )
        upload_spinner.value = False
        return app


@pn.depends(
    visualize_button.param.clicks
)
def visualize_plot(clicks):
    if select_protein.value and clicks > 0:
        visualize_spinner.value = True
        # combine selected uniprot options in one list
        uniprot_options_combined = sum([each.value for each in uniprot_options.objects if each.value], [])
        # extract all experimental data and names
        all_data = []
        all_names = []
        if preprocessed_exp_data.value is not None:
            all_data.append(preprocessed_exp_data.value)
            all_names.append(
                extract_name(os.path.splitext(os.path.basename(experimental_data.value))[0],
                             experimental_data_sample.value,
                             experimental_data_sample_name.value,
                             experimental_data_sample_name_remove_part.value
                )
            )
        if preprocessed_exp_data_2.value is not None:
            all_data.append(preprocessed_exp_data_2.value)
            all_names.append(
                extract_name(os.path.splitext(os.path.basename(experimental_data_2.value))[0],
                             experimental_data_2_sample.value,
                             experimental_data_2_sample_name.value,
                             experimental_data_2_sample_name_remove_part.value
                )
            )
        if preprocessed_exp_data_3.value is not None:
            all_data.append(preprocessed_exp_data_3.value)
            all_names.append(
                extract_name(os.path.splitext(os.path.basename(experimental_data_3.value))[0],
                             experimental_data_3_sample.value,
                             experimental_data_3_sample_name.value,
                             experimental_data_3_sample_name_remove_part.value
                )
            )
        # if only one experimental file is uploaded we need to return a string for input into plot_peptide_traces
        if len(all_data) == 1:
            all_data = all_data[0]
            all_names = all_names[0]
        if search_by.value == 'Search by a gene name':
            selected_protein = re.findall(r"\((?P<id>.+?)\)", select_protein.value)[0]
        else:
            selected_protein = select_protein.value
        # create a main figure
        fig =  plot_peptide_traces(
            df = all_data,
            name = all_names,
            protein = selected_protein,
            fasta = full_fasta,
            uniprot = full_uniprot,
            selected_features = [uniprot_feature_dict[each] for each in uniprot_options_combined],
            uniprot_feature_dict = uniprot_feature_dict,
            uniprot_color_dict = uniprot_color_dict,
            selected_proteases=proteases_options.value,
        )
        plot =  pn.Column(
            pn.Pane(
                fig,
                config={'toImageButtonOptions':
                           {'format': 'svg', # one of png, svg, jpeg, webp
                            'filename': 'custom_image',
                            'height': 500,
                            'width': 1500,
                            'scale': 1 # Multiply title/legend/axis/canvas sizes by this factor
                           }
                       },
                align='center',
                width=1500
            ),
            visualize_buttons
        )
        visualize_spinner.value = False
        return plot
    else:
        return None


@pn.depends(
    exit_button.param.clicks,
    watch=True
)
def exit_button_event(*args):
    print("Quitting server...")
    exit_button.name = "Server closed".upper()
    SERVER.stop()


def run():
    import alphamap
    global SERVER
    layout = pn.Column(
        header,
        main_part,
        upload_data,
        visualize_plot
    )
    SERVER = layout.show(threaded=True)
    print("*"*30)
    print(f"* AlphaMap {alphamap.__version__} *".center(30, '*'))
    print("*"*30)


### JS callbacks to control the behaviour of pn.Cards
uniprot_options_tab.jscallback(
    collapsed="""
        var $container = $("html,body");
        var $scrollTo = $('.uniprot_options');

        $container.animate({scrollTop: $container.offset().top + $container.scrollTop(), scrollLeft: 0},300);
        """,
    args={'card': uniprot_options_tab}
);

proteases_options_tab.jscallback(
    collapsed="""
        var $container = $("html,body");
        var $scrollTo = $('.uniprot_options');

        $container.animate({scrollTop: $container.offset().top + $container.scrollTop(), scrollLeft: 0},300);
        """,
    args={'card': proteases_options_tab}
);

additional_data_card.jscallback(
    collapsed="""
        var $container = $("html,body");
        var $scrollTo = $('.add_experim_options');

        $container.animate({scrollTop: $container.offset().top + $container.scrollTop(), scrollLeft: 0},300);
        """,
    args={'card': additional_data_card}
);

spectronaut_instructions.jscallback(
    collapsed="""
        var $container = $("html,body");
        var $scrollTo = $('.spectronaut_instr');

        $container.animate({scrollTop: $container.offset().top + $container.scrollTop(), scrollLeft: 0},300);
        """,
    args={'card': spectronaut_instructions}
);

maxquant_instructions.jscallback(
    collapsed="""
        var $container = $("html,body");
        var $scrollTo = $('.spectronaut_instr');

        $container.animate({scrollTop: $container.offset().top + $container.scrollTop(), scrollLeft: 0},300);
        """,
    args={'card': maxquant_instructions}
);


if __name__ == '__main__':
    run()