import os.path
import json
import shutil
import time
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


parser = argparse.ArgumentParser()
parser.add_argument("-m", '--model', help="this is expected model name", type=str, default="testModel")
parser.add_argument("-d", '--dir', help="this is expected target directory(empty)", type=str, default="C:\\Users\\test")
parser.add_argument("-x", '--xls', help="this is xls file path", type=str, default="..\\model_desc.xlsx")
parser.add_argument("-c", '--check', help="weather checking generated fmu file", type=str, default="yes")
args = parser.parse_args()


def check_fmu_name(model_name):
    flag = True
    if len(re.findall("[a-zA-Z0-9_]", model_name)) < len(model_name):
        flag = False
        return flag
    if len(re.findall("^[0-9_]", model_name)) > 0:
        flag = False
        return flag
    if len(re.findall("_$", model_name)) > 0:
        flag = False
        return flag
    return flag


def main():
    model_name = args.model
    target_dir = args.dir
    model_desc_file = args.xls
    # model_name = "testModel"
    # target_dir = "C:\\Users\\AVICASGT\\Desktop\\0830\\model0859"
    # model_desc_file = "..\\model_desc.xlsx"

    # check model name
    if check_fmu_name(model_name):
        print("Model name checked")
    else:
        print("Illegal model name, please specify a new model name")
        return

    # check xls file path
    if os.path.exists(model_desc_file):
        print("xlsx file checked")
    else:
        print("xlsx file does not exists")
        return

    # check target directory
    if os.path.exists(target_dir):
        if len(os.listdir(target_dir)) > 0:
            print("Please specific an empty directory")
            return
        else:
            print("Target directory checked")
    else:
        os.makedirs(target_dir)
        print("Success to create target directory")

    # convert model description file to json file
    fmu_desc = pd.read_excel(model_desc_file, sheet_name=0, header=0,
                             dtype={'name': str, 'valueRef': int, "variability": str, "causality": str,
                                    "initial": str, "typeID": str, "startValue": str, "description": str,
                                    "unit": str})
    fmu_desc = fmu_desc.fillna('')
    print(fmu_desc.shape)
    print(fmu_desc["name"].dtypes)
    json_str = '{"modelName": "src","description": "","variables": []}'
    fmu_dict = json.loads(json_str)
    for i in range(fmu_desc.shape[0]):
        data = fmu_desc.iloc[i, :]
        temp_dict = dict()
        for key in data.to_dict().keys():
            if key == "variability":
                if data["variability"] == "":
                    temp_dict["variability"] = "continuous"
            elif key == "typeID":
                print(data["typeID"])
                if data["typeID"].startswith("int"):
                    temp_dict["typeID"] = "Integer"
                elif data["typeID"].lower() == "double" or data["typeID"].lower() == "float":
                    temp_dict["typeID"] = "Real"
                elif data["typeID"].lower().startswith("bool"):
                    temp_dict["typeID"] = "Boolean"
                else:
                    raise Exception("Illegal datatype, please check fmu description")
            else:
                temp_dict[key] = data[key]
        fmu_dict["variables"].append(temp_dict)
    print(fmu_dict)
    json_text = json.dumps(fmu_dict, cls=MyEncoder)
    with open(model_name + ".input", "w") as f:
        f.write(json_text)
        print("------------")

    # move input file to target directory
    if os.path.exists(target_dir + os.path.sep + model_name + ".input"):
        os.remove(target_dir + os.path.sep + model_name + ".input")
    shutil.move(model_name + ".input", target_dir)
    gen = coreGenerator.Generator(target_dir, model_name, "FMI_template")
    gen.generate(genAddr=True)


def check_fmu():
    cwd = os.getcwd()
    fmuCheckerPath = cwd + os.path.sep + "fmuCheck.exe"
    os.system(
        fmuCheckerPath + " -e checkLog.txt " + args.dir + os.path.sep + args.model + os.path.sep + args.model + ".fmu")
    with open("checkLog.txt", "r") as f:
        lineInfo = f.readline()
        if lineInfo:
            print(lineInfo)


if __name__ == '__main__':
    main()
    if args.check == "yes":
        print("ready to check generated fmu file")
        time.sleep(1)
        check_fmu()
