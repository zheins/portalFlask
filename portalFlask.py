import os
import sys
import json
import requests
import datetime
from flask import Flask, request, g, redirect, url_for, render_template, flash

app = Flask(__name__)

app.config.from_envvar('DASH_SETTINGS', silent=False)

@app.route('/')
def home():
	if not hasattr(g, 'sample_ids'):
		g.sample_ids = get_sample_ids()
	return render_template('index.html', numsamples=len(g.sample_ids))

@app.route('/query')
def query_view():
	if not hasattr(g, 'changesets'):
		g.changesets = query_changes()
	if not hasattr(g, 'sample_ids'):
		g.sample_ids = get_sample_ids()
	return render_template('query.html', sampleids=g.sample_ids, numsamples=len(g.sample_ids))


@app.route('/query_samples', methods=['GET', 'POST'])
def query_samples_view():
	error = None
	if request.method == 'POST':
		sample_id = request.form['sampleid']
		r = requests.get(app.config['HOST'] + '/' + app.config['DB'] + '/_design/' + app.config['DESIGN_DOCUMENT'] + '/_view/' + app.config['SAMPLE_DATA_VIEW'] + '?startkey=["' + sample_id + '"]&endkey=["' + sample_id + '",{}]')
		query_result = r.json()
		return process_result(query_result, sample_id)
	flash('Invalid request')
	return redirect(url_for('query_view'))

@app.route('/charts', methods=['GET'])
def make_charts():
	if app.config.get('DATE_FILE') != None:
		date_filename = app.config['DATE_FILE'].strip()
		if not os.path.exists(date_filename):
			flash("Can't find the clinical data needed to display the charts! Please alert " + app.config['ALERT_EMAIL'])
			return redirect(url_for('home'))
		if not hasattr(g, 'timedata'):
			g.timedata = generate_timeline_data(date_filename)
		return render_template('charts.html', samples_chart_x=(x[0] for x in g.timedata), samples_chart_y=(x[1] for x in g.timedata))

	flash("Can't find the clinical data needed to display the charts! Please alert " + app.config['ALERT_EMAIL'])
	return redirect(url_for('home'))

def generate_timeline_data(date_filename):
	sample_dates = {}
	with open(date_filename, 'r') as f:
		header = f.readline().strip().split()
		print header
		sid_index = header.index('SAMPLE_ID')
		date_index = header.index('DATE_ADDED')
		for line in f:
			if line.strip() != '':
				data = line.split('\t')
				sample_dates[data[sid_index]] = datetime.datetime.strptime(data[date_index].strip(), "%Y/%m/%d").strftime("%Y-%m-%d")


	sample_dates = sorted(sample_dates.items(), key=lambda (k, v): map(int,v.split('-')))
	date_counts = {}
	num_samples = 0

	for sample, date in sample_dates:
		num_samples += 1
		date_counts[date] = num_samples

	return sorted(date_counts.items(), key=lambda (k, v): map(int,k.split('-')))


def query_changes():
	changesets = {}
	r = requests.get(app.config['HOST'] + '/' + app.config['DB'] + '/_changes')
	changes_result = r.json()
	for result in changes_result['results']:
		changesets[result['id']] = result['seq']
	return changesets

def get_latest(dict_list):
	hi = -sys.maxint-1
	higehst_value = dict_list[0]['value']
	for x, value in ((item['seq'], item['value']) for item in dict_list):
		if x > hi:
			highest_value = value
			hi = x
	return higehst_value

def process_result(query_result, sample_id):
	meta_datas = []
	cnv_intragenic_variants = []
	cnv_variants  = []
	segment_datas = []
	snp_indel_exonics = []
	snp_indel_exonic_nps = []
	snp_indel_silents = []
	snp_indel_silent_nps = []

	if 'error' in query_result.keys():
		flash('No records found matching sample id ' + sample_id)
		return redirect(url_for('query_view'))
	if len(query_result['rows']) == 0:
		flash('No records found matching sample id ' + sample_id)
		return redirect(url_for('query_view'))

	if not hasattr(g, 'changesets'):
		g.changesets = query_changes()

	for row in query_result['rows']:
		if row['key'][1] == app.config['META']:
			meta_datas.append({'seq':g.changesets[row['id']], 'value':row['value']})
		elif row['key'][1] == app.config['CNV_INTRAGENIC_VARIANTS']:
			cnv_intragenic_variants.append({'seq':g.changesets[row['id']], 'value':row['value']})
		elif row['key'][1] == app.config['CNV_VARIANTS']:
			cnv_variants.append({'seq':g.changesets[row['id']], 'value':row['value']})
		elif row['key'][1] == app.config['SNP_EXONIC']:
			snp_indel_exonics.append({'seq':g.changesets[row['id']], 'value':row['value']})
		elif row['key'][1] == app.config['SNP_EXONIC_NP']:
			snp_indel_exonic_nps.append({'seq':g.changesets[row['id']], 'value':row['value']})
		elif row['key'][1] == app.config['SNP_SILENT']:
			snp_indel_silents.append({'seq':g.changesets[row['id']], 'value':row['value']})
		elif row['key'][1] == app.config['SNP_SILENT_NP']:
			snp_indel_silent_nps.append({'seq':g.changesets[row['id']], 'value':row['value']})
		elif row['key'][1] == app.config['SEG_DATA']:
			segment_datas.append({'seq':g.changesets[row['id']], 'value':row['value']})

	latest_meta = '{[]}'
	latest_cnv_intragenic = '{[]}'
	latest_cnv_var = '{[]}'
	latest_snp_exonic = '{[]}'
	latest_snp_exonic_np = '{[]}'
	latest_snp_silent_np = '{[]}'
	latest_snp_silent = '{[]}'

	if len(meta_datas) > 0:
		latest_meta = get_latest(meta_datas)
	if len(cnv_intragenic_variants) > 0:
		latest_cnv_intragenic = get_latest(cnv_intragenic_variants)
	if len(cnv_variants) > 0:
		latest_cnv_var = get_latest(cnv_variants)
	if len(snp_indel_exonics) > 0:
		latest_snp_exonic = get_latest(snp_indel_exonics)
	if len(snp_indel_exonic_nps) > 0:
		latest_snp_exonic_np = get_latest(snp_indel_exonic_nps)
	if len(snp_indel_silents) > 0:
		latest_snp_silent = get_latest(snp_indel_silents)
	if len(snp_indel_silent_nps) > 0:
		latest_snp_silent_np = get_latest(snp_indel_silent_nps)
	if len(segment_datas) > 0:
		latest_seg_data = get_latest(segment_datas)
	
	return render_template('result.html', meta_data=json.dumps(latest_meta, indent=2, sort_keys=True, separators = (',', ': ')), 
		cnv_intragenic_variants=json.dumps(latest_cnv_intragenic, indent=2, sort_keys=True),
		cnv_variants=json.dumps(latest_cnv_var, indent=2, sort_keys=True),
		snp_indel_exonic=json.dumps(latest_snp_exonic, indent=2, sort_keys=True),
		snp_indel_exonic_np=json.dumps(latest_snp_exonic_np, indent=2, sort_keys=True),
		snp_indel_silent=json.dumps(latest_snp_silent, indent=2, sort_keys=True),
		snp_indel_silent_np=json.dumps(latest_snp_silent_np, indent=2, sort_keys=True),
		segment_data=json.dumps(latest_seg_data, indent=2, sort_keys=True),
		sample_id=sample_id)

def get_sample_ids():
	sample_ids = set()
	r = requests.get(app.config['HOST'] + '/' + app.config['DB'] + '/_design/' + app.config['DESIGN_DOCUMENT'] + '/_view/' + app.config['SAMPLE_IDS_VIEW'])
	ids_result = r.json()
	for row in ids_result['rows']:
		sample_ids.add(row['value'])
	return sample_ids		
	


