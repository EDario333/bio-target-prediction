import argparse

description = "Submit genes list to DAVID"

parser = argparse.ArgumentParser(description=description)

parser.add_argument(
    '--download-dir', '-dd', required=1,
    help='Operating system default download directory')

parser.add_argument(
    '--seqs-dir', '-sd', required=1, 
    help='SEA Search Server output directory sequences')

args = parser.parse_args()

import os
import csv
import subprocess
import time
import json
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

DOWNLOAD_DIR = args.download_dir
SEQS_DIR = args.seqs_dir

url = r'https://david.ncifcrf.gov/tools.jsp'
url_summary = r'https://david.ncifcrf.gov/summary.jsp'
genes_lists = [[]]

for root, dirs, files in os.walk(SEQS_DIR):
    for name in files:
        if name == 'cleaned-output.csv':
            reader = csv.DictReader(open(os.path.join(root, name)))
            for i in reader:
                genes_lists[len(genes_lists)-1].append((i['Name'], i['Seq ID']))
            genes_lists.append([])

genes_lists.pop()

chrome_options = webdriver.ChromeOptions()
settings = {
       "recentDestinations": [{
            "id": "Save as PDF",
            "origin": "local",
            "account": "",
        }],
        "selectedDestinationId": "Save as PDF",
        "version": 2
    }
prefs = {'printing.print_preview_sticky_settings.appState': json.dumps(settings)}
chrome_options.add_experimental_option('prefs', prefs)
chrome_options.add_argument('--kiosk-printing')

#driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), chrome_options=chrome_options)

log = open('david.log', 'w')
global_started = datetime.now()
log.write('Started: ' + global_started.strftime('%Y-%M-%d, %H:%M:%S'))

content = ''

for gen_list in genes_lists:
    driver.get(url)
    anchor_upload = driver.find_element(by=By.XPATH, value="//a[@href='Upload a Gene List or Population']")
    driver.execute_script("arguments[0].click();", anchor_upload)

    input_list = driver.find_element(by=By.ID, value='LISTBox')
    identifier_list = driver.find_element(by=By.ID, value='Identifier')
    rad_list_type_gen_list = driver.find_element(by=By.NAME, value='rbUploadType')
    submit_btn = driver.find_element(by=By.XPATH, value="//input[(@value='Submit List') and (@class = 'upload')]")
    seq_id = ''

    started = datetime.now()

    ###################################
    # Step #1: Introducing the gen list
    ###################################
    step_started = started

    for gen in gen_list:
        input_list.send_keys(gen[0])
        input_list.send_keys('\n')

        seq_id = gen[1]

    content += '\n' + '*' * 89
    content += f'\nSequence ID: {seq_id}'
    content += '\n\nStep #1: Introducing the gen list: ' + step_started.strftime('%Y-%M-%d, %H:%M:%S')

    input_list.send_keys(Keys.BACKSPACE)

    driver.execute_script("arguments[0].value = 'OFFICIAL_GENE_SYMBOL';", identifier_list)
    driver.execute_script("SpeciesSelectVisibility('OFFICIAL_GENE_SYMBOL')")

    rad_list_type_gen_list.click()
    species_select = driver.find_element(by=By.ID, value='speciesSelect')
    species_select.send_keys('Homo sapiens')
    time.sleep(2)
    species_select.send_keys(Keys.DOWN)
    species_select.send_keys(Keys.ENTER)

    finished = datetime.now()
    content += '...\nDone: ' + finished.strftime('%Y-%M-%d, %H:%M:%S')
    content += '\nElapsed time: ' + str((finished-step_started))

    ###################################
    # Step #2: Processing the gen list
    ###################################
    step_started = datetime.now()
    content += '\n\nStep #2: Processing the gen list: ' + step_started.strftime('%Y-%M-%d, %H:%M:%S')
    submit_btn.click()
    finished = datetime.now()
    content += '...\nDone: ' + finished.strftime('%Y-%M-%d, %H:%M:%S')
    content += '\nElapsed time: ' + str((finished-step_started))

    ###################################
    # Step #3: Retrieving summaries
    ###################################
    step_started = datetime.now()
    content += '\n\nStep #3: Retrieving summaries: ' + step_started.strftime('%Y-%M-%d, %H:%M:%S')
    anchor_summary = driver.find_element(by=By.XPATH, value="//a[@href='summary.jsp']")
    driver.execute_script("arguments[0].click();", anchor_summary)

    anchor_pathways = driver.find_element(by=By.XPATH, value="//a[contains(text(), 'Pathways')]")
    anchor_pathways.click()

    driver.execute_script('window.print();')

    cmds = [
        'sh', 'process-printed-file', 
        DOWNLOAD_DIR, SEQS_DIR, seq_id,
        'DAVID_ Functional Annotation Result Summary.pdf', 
        'DAVID Annotation Summary Results.pdf',
    ]
    res = subprocess.Popen(cmds, stdout=subprocess.PIPE)
    bin_output = res.communicate()
    output = bin_output[0].decode('UTF-8')
    if len(output.strip()) > 0:
        print(f'{output}\n')
        content += f'\n\n{output}\n'

    driver.get('https://david.ncifcrf.gov/annotationReport.jsp?annot=52')
    driver.execute_script('window.print();')

    cmds = [
        'sh', 'process-printed-file', 
        DOWNLOAD_DIR, SEQS_DIR, seq_id,
        'DAVID_ Database for Annotation, Visualization, and Integrated Discovery (Laboratory of Human Retrovirology and Immunoinformatics (LHRI); National Institute of Allergies and Infectious Diseases (NIAID); Leidos Biomedical Research, Inc. (LBR).pdf',
        'DAVID Functional Annotation Table.pdf',
    ]
    res = subprocess.Popen(cmds, stdout=subprocess.PIPE)
    bin_output = res.communicate()
    output = bin_output[0].decode('UTF-8')
    if len(output.strip()) > 0:
        print(f'{output}\n')
        content += f'\n\n{output}\n'

    finished = datetime.now()
    content += '...\nDone: ' + finished.strftime('%Y-%M-%d, %H:%M:%S')
    content += '\nElapsed time: ' + str((finished-step_started))

    content += '\n\nFinished gen list processing: ' + finished.strftime('%Y-%M-%d, %H:%M:%S')
    content += '\nTotal elapsed time: ' + str((finished-started))

log.write(content)

global_finished = datetime.now()
log.write('\n' + '*' * 89)
log.write('\nFinished: ' + global_finished.strftime('%Y-%M-%d, %H:%M:%S') + '\n\n')
log.write('Total elapsed time: ' + str((global_finished-global_started)))

log.close()
