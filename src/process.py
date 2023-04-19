import os
import json
import tarfile
import numpy as np
import pandas as pd
import functools as ft
from num2words import num2words
from jinja2 import Template
from s3_utils import upload_s3_file_and_generate_url

tmpl = Template(open("index.html", "r").read())

def process_dataframe_to_json(
    df,
    key,
):  
    """
    processes dataframe to output Json needed in the template
    """
    # Getting starting invoice number
    init_invoice_no = int(key.split('_')[-1].split('.')[0])

    # Filling Nan values
    df['Address'] = (df['Address']).fillna(value='')
    df['Phone No'] = df['Phone No'].fillna(value=''). \
        astype(str).replace('\.0', '', regex=True)
    df['Loading/Unloading'] = (df['Loading/Unloading']).fillna(value=0)
    df['Freight'] = (df['Freight']).fillna(value=0)
    df['Date'] = (df['Date']).dt.strftime('%m-%d-%Y').astype(str)

    # Renaming columns
    df.rename(
        columns={
            'Date': 'invoice_date',
            'Vendor': 'vendor',
            'Name': 'product_name',
            'QTY': 'product_qty',
            'AMOUNT': 'product_rate',
            'TOTAL': 'product_total',
            'Phone No': 'contact',
            'Address': 'address',
            'HSN Code': 'hsn_code',
            'Loading/Unloading': 'loading/unloading',
            'Freight': 'freight',
        }, inplace=True
    )

    # Selecting wanted or useful columns from the dataframe
    requested_variables = df[[
        'invoice_date', 'product_name', 'product_qty', 'product_rate',
        'product_total', 'vendor', 'address', 'contact', 'hsn_code',
        'loading/unloading', 'freight',
    ]]

    # Group by using invoice_date, vendor, and contact
    group_by = requested_variables.groupby(
        by=['invoice_date', 'vendor', 'contact'], sort=False)

    # Converting product details into items
    output = group_by.apply(
        lambda x: x[[
            'product_name', 'product_qty',
            'product_rate', 'product_total',
            'hsn_code'
        ]].to_json(orient="records")).rename(index='items')

    date_reset = pd.DataFrame(output).reset_index()

    # Generating freight total in a dataframe
    freight_total_df = requested_variables.groupby([
        "invoice_date", "vendor", "contact"])["freight"].sum().reset_index(
        name="freight_total")

    # Generating loading/unloading total in a dataframe
    load_unload_total_df = requested_variables.groupby([
        "invoice_date", "vendor", "contact"])[
        "loading/unloading"].sum().reset_index(
        name="loading_unloading_total")

    # Generating taxable value in a dataframe
    taxable_value_df = requested_variables.groupby([
        "invoice_date", "vendor", "contact"])[
        "product_total"].sum().reset_index(
        name="taxable_value")

    # Calculating SGST, CGST,and IGST
    sgst_percent = os.environ.get("SGST_PERCENT")
    cgst_percent = os.environ.get("CGST_PERCENT")
    igst_percent = os.environ.get("IGST_PERCENT")

    taxable_value_df['sgst_total'] = taxable_value_df.apply(
        lambda x: x['taxable_value'] * int(sgst_percent) / 100, axis=1)

    taxable_value_df['cgst_total'] = taxable_value_df.apply(
        lambda x: x['taxable_value'] * int(cgst_percent) / 100, axis=1)

    taxable_value_df['igst_total'] = taxable_value_df.apply(
        lambda x: x['taxable_value'] * int(igst_percent) / 100, axis=1)

    # Getting addresses in a dataframe
    address_df = requested_variables[[
        "invoice_date", "vendor", "contact", "address"]]

    address_df.drop_duplicates(subset=["invoice_date", "vendor", "contact"],
                               inplace=True)

    # Merging all above dataframes
    dfs = [date_reset, taxable_value_df,
           freight_total_df, load_unload_total_df, address_df]

    df_final = ft.reduce(
        lambda left, right: pd.merge(
            left, right, on=["invoice_date", "vendor", "contact"]), dfs)

    # Generating invoice numbers in a dataframe
    df_final["invoice_number"] = np.arange(
        init_invoice_no, len(df_final) + init_invoice_no).astype(str)

    df_final["invoice_number"] = df_final.apply(
        lambda x: x["invoice_date"] + "-" + x["invoice_number"], axis=1)

    # Calculating invoice total with all the taxes, etc.
    df_final["invoice_total"] = df_final.apply(
        lambda x: round(x['taxable_value'] + x['sgst_total'] + x['cgst_total'] +
                        x['igst_total'] + x['loading_unloading_total'] + x[
                            'freight_total'], 2),
        axis=1
    )

    # Converting total invoice value numerical value to words
    df_final["invoice_total_words"] = df_final.apply(
        lambda x: convert_total_value_of_the_invoice_in_words(
            x["invoice_total"]), axis=1)

    # Appending sno to the list of items
    final_list_of_dict = df_final.to_dict('index')
    final_list_of_dict_1 = list(final_list_of_dict.values())

    for lst_item in final_list_of_dict_1:
        sno = 1

        lst_item['items'] = [
            json.loads(string_dict) for string_dict in
            lst_item['items'][1:-1].replace('},{', '}|{').split('|')
        ]

        for item in lst_item['items']:
            item['sno'] = sno
            sno = sno + 1

    req_dataframe = pd.DataFrame(final_list_of_dict_1)

    req_dataframe = req_dataframe[['invoice_date', 'invoice_number', 'vendor', 'contact',
                                   'address', 'taxable_value',
                                   'sgst_total', 'cgst_total', 'igst_total',
                                   'loading_unloading_total', 'freight_total',
                                   'invoice_total', 'invoice_total_words', 'items']]

    return json.loads(req_dataframe.to_json(orient="records", indent=2))


def convert_total_value_of_the_invoice_in_words(invoice_total):
    """
    Converts invoice total from indian rupees to word format
    """
    in_words = num2words(invoice_total, lang="en_IN").title()

    return "Rupees " + in_words + " Only"


def generate_html_invoice(data):
    """
    generates the html invoice basis the vendor data supplied
    """

    html_out = tmpl.render(data)
    tmpl_name = "/tmp/{}.html".format(data["invoice_number"])

    with open(tmpl_name, "w") as f:
        f.write(html_out)

    return tmpl_name


def get_download_url_after_s3_upload(
    bucket_name,
    data_file,
    html_files
):
    """
    takes in the list of all HTML files prepared
    compresses it and uploads to S3. After uploading it will
    generate a download URL that will be valid for days specified
    as environment variables
    """

    filename = '/tmp/{}.tar.gz'.format(data_file.split('.')[0])
    out = tarfile.open(filename, mode='w')

    for _file in html_files:
        try:
            out.add(_file)
        except Exception as e:
            print(repr(e))
            continue

    out.close()

    key = "downloads/{}".format(filename)

    return upload_s3_file_and_generate_url(
        bucket_name, key, filename
    )
