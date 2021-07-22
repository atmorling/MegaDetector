#
# idfg_iwildcam_lila_prep.py
#
# Adding class labels (from the private test .csv) to the iWildCam 2019 IDFG 
# test set, in preparation for release on LILA.
#
# This version works from the iWildCam source images.
#

#%% Imports and constants

import json
import os
import numpy as np
from tqdm import tqdm

input_base = r'i:\idfg-images'
output_base = r'h:\idaho-camera-traps'

# List of images used in the iWildCam competition
iwildcam_image_list = r"h:\idaho-camera-traps\v0\iWildCam_IDFG_ml.json"

assert os.path.isfile(iwildcam_image_list)
assert os.path.isdir(input_base)
assert os.path.isdir(output_base)


#%% List files (images + .csv)

all_files_list = os.path.join(output_base,'all_files.json')
force_file_enumeration = False

if (os.path.isfile(all_files_list) and (not force_file_enumeration)):
    
    print('File list exists, bypassing enumeration')
    with open(all_files_list,'r') as f:
        all_files = json.load(f)
        
else:
    
    from pathlib import Path
    all_files = []
    for path in Path(input_base).rglob('*.*'):
        path = str(path)
        path = os.path.relpath(path,input_base)
        all_files.append(path)
    with open(all_files_list,'w') as f:
        json.dump(all_files,f,indent=1)

print('Enumerated {} files'.format(len(all_files)))

image_files = [s for s in all_files if (s.lower().endswith('.jpg') or s.lower().endswith('.jpeg'))]
csv_files = [s for s in all_files if (\
                                      (s.lower().endswith('.csv')) and \
                                      ('Backups' not in s) and \
                                      ('Metadata.csv' not in s) and \
                                      ('ExportedDataFiles' not in s) and \
                                      ('CSV Files' not in s)
                                          )]

print('{} image files, {} .csv files'.format(len(image_files),len(csv_files)))


#%% Ignore .csv files in folders with multiple .csv files

# ...which would require some extra work to decipher.

csv_files_to_ignore = []

from collections import defaultdict
folder_to_csv_files = defaultdict(list)

# fn = csv_files[0]
for fn in csv_files:
    folder_name = os.path.dirname(fn)
    folder_to_csv_files[folder_name].append(fn)

for folder_name in folder_to_csv_files.keys():
    if len(folder_to_csv_files[folder_name]) > 1:
        print('Multiple .csv files for {}:'.format(folder_name))
        for csv_file in folder_to_csv_files[folder_name]:
            print(csv_file)
            csv_files_to_ignore.append(csv_file)
        print('')
        
n_csv_original = len(csv_files)
csv_files = [s for s in csv_files if s not in csv_files_to_ignore]

print('Processing {} of {} csv files'.format(len(csv_files),n_csv_original))


#%% Parse each .csv file into sequences (prep)

import dateutil 
import pandas as pd
import datetime
 
survey_species_presence_columns = ['elkpresent','deerpresent','prongpresent']

presence_to_count_columns = {
    'otherpresent':['MooseAntlerless','MooseCalf','MooseOther','MooseBull','MooseUnkn','BlackBearAdult','BlackBearCub','LionAdult',
                    'LionKitten','WolfAdult','WolfPup','CattleCow','CattleCalf','other'],
    'elkpresent':['ElkSpike','ElkAntlerless','ElkCalf','ElkRaghorn','ElkMatBull','ElkUnkn','ElkPedNub'],
    'deerpresent':['MDbuck','MDantlerless','MDfawn','WTDbuck','WTDantlerless','WTDfawn','WTDunkn','MDunkn'],
    'prongpresent':['PronghornBuck','PronghornFawn','PHunkn']
    }

required_columns = ['File','Folder','Date','Time','otherpresent','other','otherwhat']
expected_presence_columns = ['elkpresent','deerpresent','prongpresent','humanpresent','otherpresent']
    
expected_count_columns = set()
for presence_column in presence_to_count_columns.keys():
    count_columns = presence_to_count_columns[presence_column]
    for count_column in count_columns:
        expected_count_columns.add(count_column)
        
def list_is_sorted(l):
    return all(l[i] <= l[i+1] for i in range(len(l)-1))

location_names = set()


#%% Parse each .csv file into sequences (function)

# csv_file = csv_files[-1]
def csv_to_sequences(csv_file):
    
    print('Processing {}'.format(csv_file))
    csv_file_absolute = os.path.join(input_base,csv_file)
    # os.startfile(csv_file_absolute)
    
    sequences = []
    # survey = csv_file.split('\\')[0]

    location_name = '_'.join(csv_file.split('\\')[0:-1]).replace(' ','')
    # assert location_name not in location_names
    location_names.add(location_name)
    
    # Load .csv file
    df = pd.read_csv(csv_file_absolute)
    df['datetime'] = None
    df['seq_id'] = None
    df['synthetic_frame_number'] = None
    
    column_names = list(df.columns)
    
    for s in required_columns:
        assert s in column_names
    
    count_columns = [s for s in column_names if s in expected_count_columns]
    
    presence_columns = [s for s in column_names if s.endswith('present')]
    
    for s in presence_columns:
        if s not in expected_presence_columns:
            print('Unexpected presence column {} in {}'.format(s,csv_file))
    for s in expected_presence_columns:
        if s not in presence_columns:
            print('Missing presence column {} in {}'.format(s,csv_file))
    
    for s in expected_count_columns:
        if s not in count_columns:
            print('Missing count column {} in {}'.format(s,csv_file))
        
    ## Create datetimes
    
    print('Creating datetimes')    
    
    # i_row = 0; row = df.iloc[i_row]
    for i_row,row in tqdm(df.iterrows(),total=len(df)):
        
        date = row['Date']
        time = row['Time']
        datestring = date + ' ' + time
        dt = dateutil.parser.parse(datestring)
        assert dt.year >= 2015 and dt.year <= 2019
        df.loc[i_row,'datetime'] = dt
        
    # Make sure data are sorted chronologically
    #
    # In odd circumstances, they are not... so sort them first, but warn
    datetimes = list(df['datetime'])
    if not list_is_sorted(datetimes):
        print('Datetimes not sorted for {}'.format(csv_file))
    
    df = df.sort_values('datetime') 
    df.reset_index(drop=True, inplace=True)
    datetimes = list(df['datetime'])
    assert list_is_sorted(datetimes)

    # Debugging when I was trying to see what was up with the unsorted dates    
    if False:
        for i in range(0,len(datetimes)-1):
            dt = datetimes[i+1]
            prev_dt = datetimes[i]
            delta = dt - prev_dt
            assert delta >= datetime.timedelta(0)
    
    ## Parse into sequences    
    
    print('Creating sequences')
    
    max_gap_within_sequence = 10
    current_sequence_id = None
    next_frame_number = 0
    previous_datetime = None
        
    sequence_id_to_rows = defaultdict(list)
    
    # i_row = 0; row = df.iloc[i_row]    
    for i_row,row in tqdm(df.iterrows(),total=len(df)):
        
        dt = row['datetime']
        assert dt is not None and isinstance(dt,datetime.datetime)
        
        # Start a new sequence if:
        #
        # * This image has no timestamp
        # * This image has a frame number of zero
        # * We have no previous image timestamp
        #
        if previous_datetime is None:
            delta = None
        else:
            delta = (dt - previous_datetime).total_seconds()
        
        # Start a new sequence if necessary
        if delta is None or delta > max_gap_within_sequence:
            next_frame_number = 0
            current_sequence_id = location_name + '_seq_' + str(dt) # str(uuid.uuid1())
            
        assert current_sequence_id is not None
        
        sequence_id_to_rows[current_sequence_id].append(i_row)
        df.loc[i_row,'seq_id'] = current_sequence_id
        df.loc[i_row,'synthetic_frame_number'] = next_frame_number
        next_frame_number = next_frame_number + 1
        previous_datetime = dt
        
    # ...for each row
    
    location_sequences = list(set(list(df['seq_id'])))
    location_sequences.sort()
    
    inconsistent_sequences = []
    
    
    ## Parse labels for each sequence
    
    # sequence_id = location_sequences[0]
    for sequence_id in tqdm(location_sequences):
        
        sequence_row_indices = sequence_id_to_rows[sequence_id]
        assert len(sequence_row_indices) > 0
        
        # Row indices in a sequence should be adjacent
        if len(sequence_row_indices) > 1:
            d = np.diff(sequence_row_indices)
            assert(all(d==1))
        
        # sequence_df = df[df['seq_id']==sequence_id]
        sequence_df = df.iloc[sequence_row_indices]
        
        # positive_presence_columns = None


        ## Determine what's present
        
        presence_columns_marked = []
        survey_species = []
        other_species = []
         
        for presence_column in presence_columns:
                    
            presence_values = list(sequence_df[presence_column])
            
            # The presence columns are *almost* always identical for all images in a sequence        
            single_presence_value = (len(set(presence_values)) == 1)
            # assert single_presence_value
            if not single_presence_value:
                # print('Warning: presence value for {} is inconsistent for {}'.format(presence_column,sequence_id))
                inconsistent_sequences.append(sequence_id)                
            
            if any(presence_values):
                presence_columns_marked.append(presence_column)                
                
        # ...for each presence column
        
        # Tally up the standard (survey) species
        survey_species = [s.replace('present','') for s in presence_columns_marked if s != 'otherpresent']
        
        # If no presence columns are marked, all counts should be zero
        if len(presence_columns_marked) == 0:
            
            # count_column = count_columns[0]
            for count_column in count_columns:
                
                values = list(set(list(sequence_df[count_column])))
                
                # Occasionally a count gets entered (correctly) without the presence column being marked
                # assert len(values) == 1 and values[0] == 0, 'Non-zero counts with no presence columns marked for sequence {}'.format(sequence_id)
                if (not(len(values) == 1 and values[0] == 0)):
                    print('Warning: presence and counts are inconsistent for {}'.format(sequence_id))
                    
                    # Handle this by virtually checking the "right" box
                    for presence_column in presence_to_count_columns.keys():
                        count_columns_this_species = presence_to_count_columns[presence_column]
                        if count_column in count_columns_this_species:
                            if presence_column not in presence_columns_marked:
                                presence_columns_marked.append(presence_column)
                    
                    # Make sure we found a match
                    assert len(presence_columns_marked) > 0
                
        # Handle 'other' tags
        if 'otherpresent' in presence_columns_marked:
            
            sequence_otherwhats = set()
            sequence_comments = set()
            
            for i,r in sequence_df.iterrows():            
                otherwhat = r['otherwhat']
                if isinstance(otherwhat,str):
                    otherwhat = otherwhat.strip()
                    if len(otherwhat) > 0:
                        sequence_otherwhats.add(otherwhat)
                comment = r['comment']
                if isinstance(comment,str):
                    comment = comment.strip()
                    if len(comment) > 0:
                        sequence_comments.add(comment)
                
            freetext_species = []
            for s in sequence_otherwhats:
                freetext_species.append(s)
            for s in sequence_comments:
                freetext_species.append(s)
                
            counted_species = []
            
            otherpresent_columns = presence_to_count_columns['otherpresent']
            
            # column_name = otherpresent_columns[0]
            for column_name in otherpresent_columns:
            
                if column_name in sequence_df and column_name != 'other':
            
                    column_counts = list(sequence_df[column_name])
                    column_count_positive = any([c > 0 for c in column_counts])
                    
                    if column_count_positive:
                        # print('Found non-survey counted species column: {}'.format(column_name))
                        counted_species.append(column_name)
            
            # ...for each non-empty presence column
        
            # Very rarely, the "otherpresent" column is checked, but no more detail is available
            if not ( (len(freetext_species) > 0) or (len(counted_species) > 0) ):
                other_species.append('unknown')
                
            other_species += freetext_species
            other_species += counted_species
            # other_species_string = ','.join(other_species)
            # print('Non-survey species found: {}'.format(other_species_string))
        
        # ...handling non-survey species
        
        all_species = other_species + survey_species
        if False:
            if len(all_species) > 0:
                print('Species found: {}'.format(','.join(all_species)))
                 
        # Build the sequence data
        
        images = []
        # i_row = 0; row = sequence_df.iloc[i_row]
        for i_row,row in sequence_df.iterrows():
            im = {}
            im['file_name'] = row['File']
            im['datetime'] = row['datetime']
            images.append(im)
            
        sequence = {}
        sequence['csv_source'] = csv_file
        sequence['sequence_id'] = sequence_id
        sequence['images'] = images
        sequence['species_present'] = all_species
        
        sequences.append(sequence)
        
    # ...for each sequence

    return sequences

# ...def csv_to_sequences()


#%% Parse each .csv file into sequences (loop)

from multiprocessing.pool import ThreadPool
n_threads = 1

if n_threads == 1:
    
    # csv_file = csv_files[-1]
    sequences_by_file = []
    for csv_file in csv_files:
        sequences = csv_to_sequences(csv_file)
        sequences_by_file.append(sequences)

else:
    
    pool = ThreadPool(n_threads)    
    sequences_by_file = list(tqdm(pool.imap(csv_to_sequences, csv_files), total=len(csv_files)))
    

#%% Prepare info

info = {}
info['contributor'] = 'Images acquired by the Idaho Department of Fish and Game, dataset curated by Sara Beery'
info['description'] = 'Idaho Camera traps'
info['version'] = '2021.07.19'


#%% Minor adjustments to categories

input_categories = input_data['categories']
output_categories = []

for c in input_categories:
    category_name = c['name']
    category_id = c['id']
    if category_name == 'prong':
        category_name = 'pronghorn'
    category_name = category_name.lower()
    output_categories.append({'name':category_name,'id':category_id})


#%% Create output

output_data = {}
output_data['images'] = input_data['images']
output_data['annotations'] = input_data['annotations']
output_data['categories'] = output_categories
output_data['info'] = info


#%% Write output

with open(output_json,'w') as f:
    json.dump(output_data,f,indent=2)
    

#%% Validate .json file

from data_management.databases import sanity_check_json_db

options = sanity_check_json_db.SanityCheckOptions()
options.baseDir = remote_image_base_dir
options.bCheckImageSizes = False
options.bCheckImageExistence = False
options.bFindUnusedImages = False

_, _, _ = sanity_check_json_db.sanity_check_json_db(output_json, options)


#%% Preview labels

from visualization import visualize_db

viz_options = visualize_db.DbVizOptions()
viz_options.num_to_visualize = 100
viz_options.trim_to_images_with_bboxes = False
viz_options.add_search_links = False
viz_options.sort_by_filename = False
viz_options.parallelize_rendering = True
viz_options.include_filename_links = True

# viz_options.classes_to_exclude = ['test']
html_output_file, _ = visualize_db.process_images(db_path=output_json,
                                                         output_dir=os.path.join(
                                                         base_folder,'preview'),
                                                         image_base_dir=remote_image_base_dir,
                                                         options=viz_options)
os.startfile(html_output_file)



