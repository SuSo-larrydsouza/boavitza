"""Parsers for HP DESK PDF.

See an example here https://h22235.www2.hp.com/hpinfo/globalcitizenship/environment/productdata/Countries/_MultiCountry/productcarbonfootprint_notebo_2020116223055953.pdf
"""

import logging
import re
import datetime
from typing import BinaryIO, Iterator, Dict, Any
import hashlib
import math

from tools.parsers.lib import data
from tools.parsers.lib import loader
from tools.parsers.lib import pdf
from tools.parsers.lib import text
from tools.parsers.lib import piechart_analyser


# A list of patterns to search in the text.
_HP_DESK_PATTERNS = (
    re.compile(r'Product carbon footprint (?P<name>.*?)\s*Estimated impact'),
    re.compile(r'Product (c|C)arbon (f|F)ootprint (Report)*\s*(?P<name>.{0,50}?)\s*GHG'),
    re.compile(r'Estimated impact (?P<footprint>[0-9]*)\s*kgCO2 eq.'),
    re.compile(r'herein.(?P<footprint>[0-9]*)\s*kg\s*CO2eq.'),
    re.compile(r'Other\s*organizations\s*might\s*report\s*this\s*value\s*(as)?\s*(?P<footprint_with_error>[0-9]*)\s*\+\/\-\s*(?P<tolerance>[0-9]*)\s*kg\s*of\s*CO2-e'),
    re.compile(r'Estimated\s*impact\s*(?P<footprint_with_error>[0-9]*)\s*kgCO2e(q)?\s*\+\/\-\s*(?P<tolerance>[0-9]*)\s*kg\s*(of)?\s*CO2.?e'),
    re.compile(r'Lifetime of product\s*(?P<lifetime>[0-9]*) years'),
    re.compile(r'Use location\s*(?P<use_location>(Europe|North America|China|WW|Worldwide))'),
    re.compile(r'Use energy demand \(Yearly TEC\)\s*(?P<energy_demand>[0-9]*\.[0-9]*)\s*kWh'),
    re.compile(r'Product weight\s*(?P<weight>[0-9]*\.?\s*[0-9]*)\s*kg'),
    re.compile(r'Screen size\s*(?P<screen_size>[0-9]*\.?\s*[0-9]*)\s*inches'),
    re.compile(r'Final manufacturing location\s*(?P<assembly_location>(Europe|North America|China|WW|Worldwide))\s+'),
    re.compile(r'Copyright \s*(?P<date>[0-9]{4}) '),
    re.compile(r'Use\s*(?P<gwp_use_ratio>[0-9]*\.?[0-9]*)%'),
    re.compile(r'Manufacturing\s*(?P<gwp_manufacturing_ratio>[0-9]*\.?[0-9]*)%'),
    re.compile(r'End (O|o)f Life\s*(?P<gwp_eol_ratio>[0-9]*\.?[0-9]*)%'),
    re.compile(r'Distribution\s*(?P<gwp_transport_ratio>[0-9]*\.?[0-9]*)%'),
)

_CATEGORIES = {
    'Monitor': ('Workplace', 'Monitor'),
    'Desk': ('Workplace', 'Workstation'),
    'Mobile Workstation': ('Workplace', 'Laptop'),
    'Workstation': ('Workplace', 'Workstation'),
    'Tower': ('Workplace', 'Workstation'),
    'All-in-One': ('Workplace', 'Workstation'),
    'aptop': ('Workplace', 'Laptop'),
    'ook': ('Workplace', 'Laptop'),
    'Tablet': ('Workplace', 'Tablet'),
}

_WEIGHT_PATTERNS = {
    re.compile(r'eight[^0-9]*(?P<weight>[0-9]*\.?\s*[0-9]*)'),
    re.compile(r'(?P<weight>[0-9]*\.?\s*[0-9]*)\s*(w|W)eight')
}
_LIFETIME_PATTERNS = {
    re.compile(r'Lifetime[^0-9]*(?P<lifetime>[0-9]*\.?\s*[0-9]*)'),
    re.compile(r'(?P<lifetime>[0-9])\s*Lifetime')
}
_ENERGY_PATTERNS = {
    re.compile(r'energy demand\s*(?P<energy_demand>[0-9]*\.?\s*[0-9]*)'),
    re.compile(r'(?P<energy_demand>[0-9]*\.?\s*[0-9]*)[^0-9]*nergy demand')
}
_SCREEN_PATTERNS = {
    re.compile(r'creen size[^0-9]*(?P<screen_size>[0-9]*\.?\s*[0-9]*)[^0-9]'),
    re.compile(r'(?P<screen_size>[0-9]*\.?\s*[0-9]*)[^0-9]*creen')
}
_USE_LOCATION_PATTERNS = {
    re.compile(r'Use location\s*(?P<use_location>[A-Za-z\s]*)'),
    re.compile(r'(?P<use_location>[A-Za-z ]*)\s*Use location\s*')
}
_MANUF_LOCATION_PATTERNS = {
    re.compile(r'nufacturing location\s*(?P<assembly_location>(Europe|North America|China|WW|Worldwide))'),
    re.compile(r'(?P<assembly_location>^[A-Za-z ]*)\s*(M|m)anufacturing location')
}

def parse(body: BinaryIO, pdf_filename: str) -> Iterator[data.DeviceCarbonFootprint]:
    result = data.DeviceCarbonFootprintData()
    result['comment'] = ''

    # Parse text from PDF.
    pdf_as_text = pdf.pdf2txt(body)
    extracted = text.search_all_patterns(_HP_DESK_PATTERNS, pdf_as_text)
    if not extracted:
        logging.error('The file "%s" did not match the HP pattern', pdf_filename)
        return

    # Convert each matched group to our format.
    if 'name' in extracted:
        result['name'] = extracted['name'].strip()
        for keyword, category_and_sub in _CATEGORIES.items():
            if keyword in result['name']:
                result['category'], result['subcategory'] = category_and_sub
                break
        result['name']=result['name'].replace("HP ","")
    else:
        logging.error('The file "%s" did not match the HP pattern (no name extracted)', pdf_filename)
        result['name'] = pdf_filename.split('/')[-1]  # Fallback to filename or another default value

    if not "category" in result:
            result['category'] = "Workplace"
            if 'screen_size' in extracted:
                result['subcategory'] = "Monitor"
            else:
                result['subcategory'] = "Workstation"
    if 'footprint_with_error' in extracted and 'tolerance' in extracted:
        try:
            result['gwp_total'] = float(extracted['footprint_with_error'].strip())
        except ValueError:
            result['gwp_total'] = None
        try:
            result['gwp_error_ratio'] = round(float(extracted['tolerance'].strip()) / result['gwp_total'], 4) if result['gwp_total'] else None
        except ValueError:
            result['gwp_error_ratio'] = None
    elif 'footprint' in extracted:
        try:
            result['gwp_total'] = float(extracted['footprint'].strip())
        except ValueError:
            result['gwp_total'] = None
    else:
        # Fallback when no footprint is found
        logging.error('The file "%s" did not match the HP pattern (no footprint extracted)', pdf_filename)
        result['gwp_total'] = None  # or you may choose to return/skip this file

    if 'date' in extracted:
        result['report_date'] = extracted['date']
    if 'weight' in extracted:
        result['weight'] = float(extracted['weight'].replace(' ',''))
    else:
        for block, page in pdf.search_text(body, 'weight'):
            temp_text = page.get_textbox((block.x0, block.y0 - 2, block.x1 + 150, block.y1 + 2))
            extracted_weight = text.search_all_patterns(_WEIGHT_PATTERNS, temp_text)
            if 'weight' in extracted_weight:
                result['weight']=extracted_weight['weight']
                break
    if 'screen_size' in extracted:
        result['screen_size'] = float(extracted['screen_size'])
    else:
        for block, page in pdf.search_text(body, 'screen size'):
            temp_text = page.get_textbox((block.x0, block.y0 - 2, block.x1 + 150, block.y1 + 2))
            extracted_temp = text.search_all_patterns(_SCREEN_PATTERNS, temp_text)
            if 'screen_size' in extracted_temp:
                result['screen_size']=extracted_temp['screen_size']
                break
    if 'assembly_location' in extracted:
        result['assembly_location'] = extracted['assembly_location']
    else:
        for block, page in pdf.search_text(body, 'manufacturing location'):
            temp_text = page.get_textbox((block.x0, block.y0 - 2, block.x1 + 160, block.y1 + 2))
            extracted_temp = text.search_all_patterns(_MANUF_LOCATION_PATTERNS, temp_text)
            if 'assembly_location' in extracted_temp:
                result['assembly_location']=extracted_temp['assembly_location']
                break
    if 'lifetime' in extracted:
        result['lifetime'] = float(extracted['lifetime'])
    else:
        for block, page in pdf.search_text(body, 'lifetime of pro'):
            temp_text = page.get_textbox((block.x0, block.y0 - 2, block.x1 + 150, block.y1 + 2))
            extracted_temp = text.search_all_patterns(_LIFETIME_PATTERNS, temp_text)
            if 'lifetime' in extracted_temp:
                result['lifetime']=float(extracted_temp['lifetime'])
                break
    if 'use_location' in extracted:
        result['use_location'] = extracted['use_location']
    else:
        for block, page in pdf.search_text(body, 'use location'):
            temp_text = page.get_textbox((block.x0, block.y0 - 2, block.x1 + 160, block.y1 + 2))
            extracted_temp = text.search_all_patterns(_USE_LOCATION_PATTERNS, temp_text)
            if 'use_location' in extracted_temp:
                result['use_location']=extracted_temp['use_location']
                break
    if 'energy_demand' in extracted:
        energy_demand_str = extracted['energy_demand'].strip()
        if energy_demand_str:
            result['yearly_tec'] = float(energy_demand_str)
        else:
            result['yearly_tec'] = None  # or a default value
    else:
        for block, page in pdf.search_text(body, 'energy demand'):
            temp_text = page.get_textbox((block.x0, block.y0 - 2, block.x1 + 150, block.y1 + 2))
            extracted_temp = text.search_all_patterns(_ENERGY_PATTERNS, temp_text)
            if 'energy_demand' in extracted_temp:
                energy_demand_str = extracted_temp['energy_demand'].strip()
                if energy_demand_str:
                    result['yearly_tec'] = float(energy_demand_str)
                    break

    if 'gwp_manufacturing_ratio' in extracted:
        result['gwp_manufacturing_ratio'] = float(extracted['gwp_manufacturing_ratio'])/100
    if 'gwp_use_ratio' in extracted:
        result['gwp_use_ratio'] = float(extracted['gwp_use_ratio'])/100
    if 'gwp_eol_ratio' in extracted:
        result['gwp_eol_ratio'] = float(extracted['gwp_eol_ratio'])/100
    if 'gwp_transport_ratio' in extracted:
        result['gwp_transport_ratio'] = float(extracted['gwp_transport_ratio'])/100  
   
    now = datetime.datetime.now()
    result['added_date'] = now.strftime('%Y-%m-%d')
    result['add_method'] = "HP Auto Parser"
    result['manufacturer'] = "HP"

    needed_ratios = [
        'gwp_manufacturing_ratio',
        'gwp_use_ratio',
        'gwp_eol_ratio',
        'gwp_transport_ratio',
        'gwp_chassis_ratio',
        'gwp_display_ratio',
        'gwp_electronics_ratio',
        'gwp_packaging_ratio',
        'gwp_psu_ratio',
    ]

    if not all(key in result for key in needed_ratios):
        unpie = piechart_analyser.PiechartAnalyzer(debug=0)

        pie_data: Dict[str, Any] = {}
        for image in pdf.list_images(body):
            md5 = hashlib.md5(image).hexdigest()
            if md5 == 'aa44d95aad83a5871bd7974cafd63a06':
                continue
            unpie_output = unpie.analyze(image, ocrprofile='HP')
            if unpie_output and len(unpie_output.keys()) > len(pie_data.keys()):
                pie_data = unpie_output
                if 'use' in pie_data:
                    break

        if not pie_data:
            # try with full page rendering
            image = pdf.pdf2img(body, 0)
            rows, columns, depth = image.shape
            bottom_half = image[int(rows/2):, :, :].copy()
            pie_data = unpie.analyze(bottom_half, ocrprofile='HP')
        
        # Even if pie_data is partially filled, try to complete it
        if not 'prod' in pie_data:
            pie_data = unpie.auto_prod(pie_data)

        # Only update result if pie_data has meaningful entries
        if any(value > 0 for value in pie_data.values() if isinstance(value, (int, float))):
            result = unpie.append_to_boavizta(result, pie_data)



    # Apply some automatic fixes
    if 'gwp_use_ratio' in result and 'yearly_tec' in result and result.get('gwp_total'):
        # compute electricity factor assuming 100% of the 'use' phase comes from the electricity consumption,
        elec_factor = result['gwp_use_ratio'] * result['gwp_total'] / (result['lifetime'] * result['yearly_tec'])
        if math.isfinite(elec_factor):
            # Fix #1: for some items, the reported lifetime does not
            # match the one used for the computation, leading to odd elecfactor.
            # Those can be identified by computing what would have been the
            # lifetime for a factor of 0.686kgCO2e/kWh and checking this
            # number is roughly an integer
            for expected_factor in [0.686, 0.525]:
                expected_lifetime = elec_factor * result['lifetime'] / expected_factor
                if (elec_factor<0.52 or elec_factor>0.695) and (abs(expected_lifetime-result['lifetime'])>0.6) and abs(expected_lifetime-round(expected_lifetime))<0.1:
                    result['lifetime'] = round(expected_lifetime)
                    result['comment'] = ' '.join([result['comment'], "fixed lifetime"])
                    elec_factor = result['gwp_use_ratio'] * result['gwp_total'] / (result['lifetime'] * result['yearly_tec'])
                    break

            # Problem #2: for many items, there is a odd discrepancy between
            # the reported CO2e values (mean & percentiles) and the mean gwp_total obtained
            # by summing up the values of the bar plots. For those items, we can
            # also observe that the percentages of the pie-chart match the percentage
            # of the bar plot. Moreover, the 'use' phase of the bar-plot can also be
            # properly recovered from "yearly_tec * lifetime * 0.525kgCO2e/kWh"
            # -> Those observations suggest that the bar plots are corrects,
            #    but that the global mean (and percentiles) are not correct.
            # -> It is important to correct this error as it also impact the embodied values.
            # Those items can be found from the estimated electricity factor which is around
            # 0.42 for those erroneous files.
            if elec_factor > 0.34 and elec_factor < 0.46:
                correction_factor = 0.525 / elec_factor
                result['gwp_total'] *= correction_factor
                result['comment'] = ' '.join([result['comment'], "fixed gwp_total"])

    yield data.DeviceCarbonFootprint(result)


# Convenient way to run this scraper as a standalone.
if __name__ == '__main__':
    loader.main(parse)