import os.path
import zipfile
from xml.dom.minidom import parseString
import json
import shutil
import coreGenerator
import argparse
import re
import pandas as pd
import numpy as np


class MyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return super(MyEncoder, self).default(obj)


def get_model_stat_by_fmu(fmu_file):
    azip = zipfile.ZipFile(fmu_file)
    xml_info = azip.getinfo("modelDescription.xml")
    md = azip.open(xml_info)
    xml_string = md.read().decode("utf-8")
    dom = parseString(xml_string)
    data = dom.documentElement
    vars = data.getElementsByTagName("ScalarVariable")
    json_dict = dict()
    json_dict["name"] = "testModel"
    json_dict["description"] = ""
    json_dict["variables"] = []
    stat_dict = {"input_boolean": 0, "input_double": 0, "input_int": 0, "input_string": 0,
                 "output_boolean": 0, "output_double": 0, "output_int": 0, "output_string": 0}
    for var in vars:
        cal = var.getAttribute("causality")
        name = var.getAttribute("name")
        inttype = var.getElementsByTagName("Integer")
        booltype = var.getElementsByTagName("Boolean")
        realtype = var.getElementsByTagName("Real")
        strtype = var.getElementsByTagName("String")
        temp_dict = dict()
        temp_dict["valueRef"] = -1
        temp_dict["variability"] = var.getAttribute("variability")
        temp_dict["initial"] = var.getAttribute("initial")
        temp_dict["name"] = name
        if cal == "input":
            temp_dict["causality"] = "input"
            if len(inttype) > 0:
                temp_dict["typeID"] = "Integer"
                stat_dict["input_int"] += 1
            elif len(booltype) > 0:
                temp_dict["typeID"] = "Boolean"
                stat_dict["input_boolean"] += 1
            elif len(realtype) > 0:
                temp_dict["typeID"] = "Real"
                stat_dict["input_double"] += 1
            elif len(strtype) > 0:
                temp_dict["typeID"] = "String"
                stat_dict["input_string"] += 1
        elif cal == "output":
            temp_dict["causality"] = "output"
            if len(inttype) > 0:
                temp_dict["typeID"] = "Integer"
                stat_dict["output_int"] += 1
            elif len(booltype) > 0:
                temp_dict["typeID"] = "Boolean"
                stat_dict["output_boolean"] += 1
            elif len(realtype) > 0:
                temp_dict["typeID"] = "Real"
                stat_dict["output_double"] += 1
            elif len(strtype) > 0:
                temp_dict["typeID"] = "String"
                stat_dict["output_string"] += 1
        else:
            continue
        temp_dict["startValue"] = "0"
        temp_dict["description"] = ""
        temp_dict["uint"] = ""
        json_dict["variables"].append(temp_dict)
    return stat_dict, json_dict


def get_model_stat_by_xls(xls_file):
    xls_info = pd.read_excel(xls_file, sheet_name=0, header=0,
                             dtype={'name': str, 'valueRef': int, "variability": str, "causality": str,
                                    "initial": str, "typeID": str, "startValue": str, "description": str,
                                    "unit": str})
    xls_info = xls_info.fillna('')
    json_str = '{"modelName": "src","description": "","variables": []}'
    json_dict = json.loads(json_str)
    stat_dict = {"input_boolean": 0, "input_double": 0, "input_int": 0, "input_string": 0,
                 "output_boolean": 0, "output_double": 0, "output_int": 0, "output_string": 0}
    for row in range(xls_info.shape[0]):
        row_data = xls_info.iloc[row, :].to_dict()
        temp_dict = dict()
        if row_data["causality"].lower() == "input":
            if row_data["typeID"].startswith("int"):
                stat_dict["input_int"] += 1
            elif row_data["typeID"].lower() == "double" or row_data["typeID"].lower() == "float":
                stat_dict["input_double"] += 1
            elif row_data["typeID"].lower().startswith("bool"):
                stat_dict["input_boolean"] += 1
            elif row_data["typeID"].lower().startswith("str"):
                stat_dict["input_string"] += 1
        if row_data["causality"].lower() == "output":
            if row_data["typeID"].startswith("int"):
                stat_dict["output_int"] += 1
            elif row_data["typeID"].lower() == "double" or row_data["typeID"].lower() == "float":
                stat_dict["output_double"] += 1
            elif row_data["typeID"].lower().startswith("bool"):
                stat_dict["output_boolean"] += 1
            elif row_data["typeID"].lower().startswith("str"):
                stat_dict["output_string"] += 1
            else:
                raise Exception("Illegal datatype,please check xls typeID")
        for key in row_data.keys():
            if key == "variability":
                if row_data["variability"] == "":
                    temp_dict["variability"] = "continuous"
                else:
                    temp_dict["variability"] = row_data["variability"]
            elif key == "typeID":
                if row_data["typeID"].startswith("int"):
                    temp_dict["typeID"] = "Integer"

                elif row_data["typeID"].lower() == "double" or row_data["typeID"].lower() == "float":
                    temp_dict["typeID"] = "Real"

                elif row_data["typeID"].lower().startswith("bool"):
                    temp_dict["typeID"] = "Boolean"

                else:
                    raise Exception("Illegal datatype,please check xls typeID")
            else:
                temp_dict[key] = row_data[key]
        json_dict["variables"].append(temp_dict)
    return stat_dict, json_dict


def gen_source_json(xls_file, *fmu_list):
    xls_stat_dict = get_model_stat_by_xls(xls_file)[0]
    print("xls_info: ", xls_stat_dict)

    all_fmus_dict = {"input_boolean": 0, "input_double": 0, "input_int": 0, "input_string": 0,
                     "output_boolean": 0, "output_double": 0, "output_int": 0, "output_string": 0}
    for fmu in fmu_list:
        fmu_stat_dict = get_model_stat_by_fmu(fmu)[0]
        for key in fmu_stat_dict.keys():
            all_fmus_dict[key] += fmu_stat_dict[key]
    print("all_fmu_info: ", all_fmus_dict)

    source_dict = dict()
    for key in xls_stat_dict.keys():
        if key.startswith("input"):
            if key == "input_boolean" and xls_stat_dict[key] != 0:
                if xls_stat_dict["input_boolean"] - all_fmus_dict["output_boolean"] > 0:
                    source_dict["output_boolean"] = xls_stat_dict["input_boolean"] - all_fmus_dict["output_boolean"]
                # else:
                #     raise Exception("The fmus outputs cannot satisfy xls inputs")
            elif key == "input_double" and xls_stat_dict[key] != 0:
                if xls_stat_dict["input_double"] - all_fmus_dict["output_double"] > 0:
                    source_dict["output_double"] = xls_stat_dict["input_double"] - all_fmus_dict["output_double"]
                # else:
                #     raise Exception("The fmus outputs cannot satisfy xls inputs")
            elif key == "input_int" and xls_stat_dict[key] != 0:
                if xls_stat_dict["input_int"] - all_fmus_dict["output_int"] > 0:
                    source_dict["output_int"] = xls_stat_dict["input_int"] - all_fmus_dict["output_int"]
                # else:
                #     raise Exception("The fmus outputs cannot satisfy xls inputs")
            elif key == "input_string" and xls_stat_dict[key] != 0:
                if xls_stat_dict["input_string"] - all_fmus_dict["output_string"] > 0:
                    source_dict["output_string"] = xls_stat_dict["input_string"] - all_fmus_dict["output_string"]
                # else:
                #     raise Exception("The fmus outputs cannot satisfy xls inputs")
    print("source_info: ", source_dict)
    json_str = '{"modelName": "source","description": "","variables": []}'
    json_dict = json.loads(json_str)
    idx = 1
    for key in source_dict.keys():
        for i in range(source_dict[key]):
            temp_dict = dict()
            temp_dict["name"] = "output" + str(idx)
            idx += 1
            temp_dict["variability"] = "continuous"
            temp_dict["valueRef"] = -1
            temp_dict["causality"] = "output"
            temp_dict["initial"] = "1"
            temp_dict["startValue"] = "1"
            temp_dict["description"] = ""
            temp_dict["unit"] = ""
            if key.split("_")[1] == "boolean":
                temp_dict["typeID"] = "Boolean"
            elif key.split("_")[1] == "double":
                temp_dict["typeID"] = "Real"
            elif key.split("_")[1] == "int":
                temp_dict["typeID"] = "Integer"
            elif key.split("_")[1] == "string":
                temp_dict["typeID"] = "String"
            json_dict["variables"].append(temp_dict)
    print(json_dict)
    json_text = json.dumps(json_dict, cls=MyEncoder)
    with open("source.input", "w") as f:
        f.write(json_text)
    return source_dict, json_dict


def main():
    target_dir = "C:\\Users\\AVICASGT\\Desktop\\src_model"
    fmu1 = "ATA24_ASG.fmu"
    fmu2 = "ATA24_RAT.fmu"
    fmu3 = "ATA24_VFG.fmu"
    xls = "model_desc.xlsx"
    gen_source_json(xls, fmu1, fmu2, fmu3)

    if os.path.exists(target_dir + os.path.sep + "source.input"):
        os.remove(target_dir + os.path.sep + "source.input")
    shutil.move("source.input", target_dir)
    gen = coreGenerator.Generator(targetDir=target_dir, modelName="source", tmpltFolderName="SRC_template")
    gen.generate()


if __name__ == '__main__':
    main()
    os.system("fmuCheck.exe -e srcCheckLog.txt C:\\Users\\AVICASGT\\Desktop\\src_model\\source\\source.fmu")
