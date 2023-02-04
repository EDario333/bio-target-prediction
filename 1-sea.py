import argparse

description = """Process each SMILE sequence in the Similarity 
ensemble approach (SEA) server""".replace('\n', '')

parser = argparse.ArgumentParser(description=description)

parser.add_argument(
    '--download-dir', '-dd', required=1,
    help='Operating system default download directory')

parser.add_argument(
    '--seqs-dir', '-sd', required=1, help='SMILES sequences directory')

parser.add_argument(
    '--max-exec-time', '-met', required=1, type=int,
    help='Maximum execution time per sequence to be processed in SEA (in seconds)')

args = parser.parse_args()

import os
import sys
import csv
import subprocess
import time
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

MAX_EXECUTION_TIME = args.max_exec_time  # secs.
DOWNLOAD_DIR = args.download_dir
SEQS_DIR = args.seqs_dir

# Took from: https://stackoverflow.com/a/51949811
def download_wait(directory:str, timeout:int, nfiles:int=None):
    """
    Wait for downloads to finish with a specified timeout.

    Args
    ----
    directory : str
        The path to the folder where the files will be downloaded.
    timeout : int
        How many seconds to wait until timing out.
    nfiles : int, defaults to None
        If provided, also wait for the expected number of files.
    """
    seconds = 0
    dl_wait = True
    while dl_wait and seconds < timeout:
        time.sleep(1)
        dl_wait = False
        files = os.listdir(directory)
        if nfiles and len(files) != nfiles:
            dl_wait = True

        for fname in files:
            if fname.endswith('.crdownload'):
                dl_wait = True

        seconds += 1
    return seconds

url = r'https://sea.bkslab.org'
seqs = []

for i in os.scandir(SEQS_DIR):
    if i.is_file() and i.path.endswith('.smi'):
        f = open(i.path)
        seqs.append({
            'id': i.path[i.path.rfind('/')+1:i.path.rfind('.smi')], 
            'seq': f.read()})

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
driver.get(url)

input_smiles = driver.find_element(by=By.NAME, value='query_custom_targets_paste')
submit_btn = driver.find_element(by=By.XPATH, value="//button[(@type='submit') and (@class = 'btn btn-primary btn-lg')]")

log = open('log', 'a')
global_started = datetime.now()
log.write('Started: ' + global_started.strftime('%Y-%M-%d, %H:%M:%S') + '\n')

for seq in seqs:
    content = ''
    seq_ = seq['seq']
    input_smiles.send_keys(seq_)
    submit_btn.click()

    download_results_btn = None
    total_seconds = 0
    started = datetime.now()

    content += '\n' + '*' * 89
    content += '\nStarting sequence processing: ' + started.strftime('%Y-%M-%d, %H:%M:%S') + '\n'
    content += 'Sequence ID: ' + seq['id']
    started = datetime.now()

    ###################################
    # Step #1: Processing at SEA
    ###################################
    step_started = started
    content += '\n\nStep #1: Processing at SEA: ' + step_started.strftime('%Y-%M-%d, %H:%M:%S')

    while not download_results_btn and total_seconds < MAX_EXECUTION_TIME:
        try:
            download_results_btn = driver.find_element(by=By.XPATH, value="//i[@class = 'glyphicon glyphicon-download-alt pull-right']")
        except NoSuchElementException as e:
            finished = datetime.now()
            etime = (finished-started)
            total_seconds = etime.total_seconds()

    finished = datetime.now()

    fs_log = None

    if download_results_btn:
        content += '...\nDone: ' + finished.strftime('%Y-%M-%d, %H:%M:%S')
        content += '\nElapsed time: ' + str((finished-step_started))

        ###################################
        # Step #2: Downloading from SEA
        ###################################
        download_results_btn.click()
        step_started = datetime.now()
        content += '\n\nStep #2: Downloading from SEA: ' + step_started.strftime('%Y-%M-%d, %H:%M:%S')
        download_wait(DOWNLOAD_DIR, MAX_EXECUTION_TIME)
        finished = datetime.now()
        content += '...\nDone: ' + finished.strftime('%Y-%M-%d, %H:%M:%S')
        content += '\nElapsed time: ' + str((finished-step_started))

        download_url = driver.current_url
        fname = download_url[download_url.rfind('/')+1:]

        ###################################
        # Step #3: Extracting
        ###################################
        cmds = [
            'sh', 'process-downloaded-file', 
            DOWNLOAD_DIR, fname, seq['id'],
        ]
        step_started = datetime.now()
        content += '\n\nStep #3: Extracting: ' + step_started.strftime('%Y-%M-%d, %H:%M:%S')
        res = subprocess.Popen(cmds, stdout=subprocess.PIPE)
        bin_output = res.communicate()
        output = bin_output[0].decode('UTF-8')
        print(f'{output}\n')
        content += f'\n\n{output}\n'
        finished = datetime.now()
        content += 'Done: ' + finished.strftime('%Y-%M-%d, %H:%M:%S')
        content += '\nElapsed time: ' + str((finished-step_started))

        ###################################
        # Step #4: Formatting output.csv (Target ID & Name)
        ###################################
        fname = seq['id']

        step_started = datetime.now()
        content += '\n\nStep #4: Formatting output.csv (Target ID & Name): ' + step_started.strftime('%Y-%M-%d, %H:%M:%S')
        reader = csv.DictReader(open(f'{fname}/sea-results.xls'))
        fw = open(f'{fname}/output.csv', 'a')
        writer = csv.DictWriter(fw, fieldnames=['Target ID', 'Name'])
        writer.writeheader()

        fwc = open(f'{fname}/cleaned-output.csv', 'a')
        cleaned_writer = csv.DictWriter(fwc, fieldnames=['Target ID', 'Name', 'Seq ID'])
        cleaned_writer.writeheader()

        for i in reader:
            writer.writerow({'Target ID': i['Target ID'], 'Name': i['Name']})
            if len(i['Name'].strip()) > 0:      # because there are empty cells
                """
                Next line is to ignore those with - 
                (for instance: HLA-DRB3, HLA-A). I think is not possible to "clean" 
                those, because not always is just remove the -:
                * HLA-DRB3 becomes in DRB3
                * HLA-A becomes in HLAA
                """
                if '-' not in i['Name']:
                    cleaned_writer.writerow({'Target ID': i['Target ID'], 'Name': i['Name'], 'Seq ID': seq['id']})

        fw.close()
        fwc.close()

        finished = datetime.now()
        content += '...\nDone: ' + finished.strftime('%Y-%M-%d, %H:%M:%S')
        content += '\nElapsed time: ' + str((finished-step_started))

        finished = datetime.now()
        content += '\n\nFinished sequence processing: ' + finished.strftime('%Y-%M-%d, %H:%M:%S')
        content += '\nTotal elapsed time: ' + str((finished-started))

        fs_log = open(f"{fname}/{seq['id']}.log", 'w')
    else:
        print(f'\nEmpty results for sequence: {seq}')
        sys.stderr.write(f'\nEmpty results for sequence: {seq}')
        content += f'... Empty results for sequence {seq}: ' + finished.strftime('%Y-%M-%d, %H:%M:%S')
        fs_log = open(f"{seq['id']}.log", 'w')

    log.write(content)
    fs_log.write(content)
    fs_log.close()

    driver.get(url)
    input_smiles = driver.find_element(by=By.NAME, value='query_custom_targets_paste')
    submit_btn = driver.find_element(by=By.XPATH, value="//button[(@type='submit') and (@class = 'btn btn-primary btn-lg')]")

global_finished = datetime.now()
log.write('\n' + '*' * 89)
log.write('\nFinished: ' + global_finished.strftime('%Y-%M-%d, %H:%M:%S') + '\n\n')
#log.write('Total elapsed time: ' + str((global_finished-global_started).seconds) + ' (secs.)\n')
log.write('Total elapsed time: ' + str((global_finished-global_started)))

log.close()
