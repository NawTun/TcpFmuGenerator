import sys
import shutil
import uuid
import time
import json
import datetime
import os
import xml.etree.ElementTree as ET

# The directory name of the FMI_template folder
TEMPLATE_FOLDER_NAME = "FMI_template"


class VarDef:
    """Contains all properties of a scalar variable in the model description."""

    def __init__(self):
        self.name = ""
        self.valueRef = -1  # means automatic enumeration of value references
        self.variability = ""  # constant, fixed, tunable, discrete, continuous
        self.causality = ""  # parameter, calculatedParameter, input, output, local, independent
        self.initial = ""  # exact, approx, calculated
        self.typeID = ""  # Real, Integer, Boolean, String
        self.description = ""  # an optional description of the variable's meaning
        self.unit = ""  # the unit, only for Real-type variables
        self.startValue = ""

    def __init__(self, name, variability, causality, initial, typeID):
        self.name = name
        self.valueRef = -1
        self.variability = variability
        self.causality = causality
        self.initial = initial
        self.typeID = typeID
        self.description = ""  # an optional description of the variable's meaning
        self.unit = ""  # the unit, only for Real-type variables
        self.startValue = ""

    def toJson(self):
        return {
            "name": self.name,
            "valueRef": self.valueRef,
            "variability": self.variability,
            "causality": self.causality,
            "initial": self.initial,
            "typeID": self.typeID,
            "startValue": self.startValue,
            "description": self.description,
            "unit": self.unit
        }


def varDefFromJson(data):
    v = VarDef(data['name'], data['variability'], data['causality'], data['initial'], data['typeID'])
    if 'unit' in data:
        v.unit = data['unit']
    if 'description' in data:
        v.description = data['description']
    v.startValue = data['startValue']
    v.valueRef = data['valueRef']
    return v


class Generator:
    """Class that encapsulates all parameters needed to generate the FMU.

    Usage: create class instance, set member variables, call function generate()
    """

    def __init__(self, targetDir, modelName, tmpltFolderName):
        """ Constructor, initializes member variables.

        Member variables:

        targetDir -- Target directory can be relative (to current working directory) or
                     absolute. FMU directory is created below this directory, for example:
                        <target path>/<modelName>/
                     By default, target path is empty which means that the subdirectory <modelName>
                     is created directly below the current working directory.
        modelName -- A user defined model name
        description -- A user defined description
        variables -- vector of type VarDefs with variable definitions (inputs, outputs, parameters)
        numberOfContinuousStates -- number of continuous states in the model (only exposed for ModelExchange functionality)
        """
        self.targetDir = targetDir
        self.tmpltFolderName = tmpltFolderName
        self.modelName = modelName
        self.description = ""
        self.variables = []
        self.messages = []
        self.numberOfContinuousStates = 0
        self.lineSep = "####################################################"

    def printMsg(self, text):
        print(text)
        self.messages.append(text)

    def generate(self, genAddr=False):

        """ Main FMU generation function. Requires member variables to be set correctly.

        Functionality: first a FMI_template folder structure is copied to the target location. Then,
        placeholders in the original files are substituted.

        Target directory is generated using targetDir member variable, for relative directory,
        the target directory is created from `<current working directory>/<targetDir>/<modelName>`.
        For absolute file paths the target directory is `<targetDir>/<modelName>`.
        """
        input_file = os.path.join(self.targetDir, self.modelName + ".input")
        self.readInputData(targetFile=input_file)

        # sanity checks
        if self.modelName == "":
            raise RuntimeError("Missing model name")

        # compose target directory: check if self.targetPath is an absolute file path
        if os.path.isabs(self.targetDir):
            self.targetDirPath = os.path.join(self.targetDir, self.modelName)
        else:
            self.targetDirPath = os.path.join(os.getcwd(), self.targetDir)
            self.targetDirPath = os.path.join(self.targetDirPath, self.modelName)

        self.printMsg("Target directory   : {}".format(self.targetDirPath))

        # the source directory with the FMI_template files is located relative to
        # this python script: ../data/FMIProject

        # get the path of the current python script
        scriptPath = os.path.dirname(os.path.abspath(__file__))
        self.printMsg("Script path        : {}".format(scriptPath))

        # relative path (from script file) to resource/FMI_template directory
        templateDirPath = os.path.join(scriptPath, self.tmpltFolderName)
        templateDirPath = os.path.abspath(templateDirPath)
        self.printMsg("Template location  : {}".format(templateDirPath))

        # user may have specified "FMI_template" as model name
        # (which would be weird and break the code, hence a warning)
        if self.modelName == "FMI_template":
            self.printMsg("WARNING: model name is same as FMI_template folder name. This may not work!")

        # store input data into <targetDir>/<modelName>.input so that it can be read again by wizard to
        # populate input data
        self.writeInputData(self.targetDirPath + ".input")

        self.printMsg("Copying FMI_template directory to target directory (and renaming files)")
        self.copyTemplateDirectory(templateDirPath)

        self.printMsg("Generating unique value references")
        # first create a set of all predefined valueReferences
        valueRefs = set()
        for var in self.variables:
            if var.valueRef != -1:
                valueRefs.add(var.valueRef)
        # start auto-numbering from valueRef 1
        nextValueRef = 1
        for var in self.variables:
            # generate value if auto-numbered
            if var.valueRef == -1:
                # find first unused index
                i = nextValueRef
                while i in valueRefs:
                    i = i + 1
                nextValueRef = i
                valueRefs.add(i)  # add value ref to set of already used valueRefs
                var.valueRef = nextValueRef  # remember assigned value reference

        self.printMsg("Adjusting FMI_template files (replacing placeholders)")
        self.substitutePlaceholders()
        self.postProcess()
        if genAddr:
            self.generateAddrConfig()

    def postProcess(self):
        print(self.lineSep)
        self.printMsg("Ready to cmake")
        # print('cmake -G "MinGW Makefiles" -S ' + self.targetDirPath + " -B " + self.targetDirPath + os.path.sep + "new")
        # print(os.getenv('path'))
        # os.system(
        #     'cmake -G "MinGW Makefiles" -S ' + self.targetDirPath + " -B " + self.targetDirPath + os.path.sep + "new")
        # self.printMsg("Success to create makefile")
        os.system(
            'cmake -S ' + self.targetDirPath + " -B " + self.targetDirPath + os.path.sep + "new")
        self.printMsg("Success to create msvc project")
        print(self.lineSep)
        # self.printMsg("Ready to make")
        self.printMsg("Ready to build")
        # os.system(
        #     "make -C " + self.targetDirPath + os.path.sep + "new")
        os.system(
            "devenv " + self.targetDirPath + os.path.sep + "new" + os.path.sep + self.modelName + ".sln /build")
        self.printMsg("Success to make library")
        print(self.lineSep)
        self.printMsg("Ready to process modelDescription.xml")
        # delete model_exchange tag in modelDescription.xml
        try:
            xml_path = self.targetDirPath + os.path.sep + "data" + os.path.sep + "modelDescription.xml"
            tree = ET.parse(xml_path)
            root = tree.getroot()
            del_tag = root.findall('ModelExchange')
            root.remove(del_tag[0])
            ##adjust initial
            moldelVarTag = root.findall("ModelVariables")
            scalarVarTag = moldelVarTag[0].findall("ScalarVariable")
            for i in scalarVarTag:
                if i.get("causality") == "input":
                    del i.attrib["initial"]
                elif i.get("causality") == "output":
                    i.set("initial", "calculated")
                    boolTag = i.findall("Boolean")
                    realTag = i.findall("Real")
                    if (len(boolTag) > 0):
                        del boolTag[0].attrib["start"]
                    if (len(realTag) > 0):
                        del realTag[0].attrib["start"]
                else:
                    pass
            tree.write(xml_path)
            self.printMsg("Success to process modelDescription.xml")
        except Exception as e:
            self.printMsg(str(e))
            raise RuntimeError("Error processing xml file.")

        print(self.lineSep)
        self.printMsg("Ready to package fmu")
        os.makedirs(self.targetDirPath + os.path.sep + "fmu_dir" + os.path.sep + "binaries" + os.path.sep + "win64")
        shutil.copyfile(
            self.targetDirPath + os.path.sep + "new" + os.path.sep + "Debug" + os.path.sep + self.modelName + ".dll",
            self.targetDirPath + os.path.sep + "fmu_dir" + os.path.sep + "binaries" + os.path.sep + "win64" + os.path.sep + self.modelName + ".dll")
        print("Success to copy ", self.modelName + ".dll")
        shutil.copy(self.targetDirPath + os.path.sep + "data" + os.path.sep + "modelDescription.xml",
                    self.targetDirPath + os.path.sep + "fmu_dir" + os.path.sep + "modelDescription.xml")
        print("Success to copy modelDescription.xml")
        print(self.lineSep)
        self.printMsg("Packaging")
        zip_arc = "7z a " + self.targetDirPath + os.path.sep + "fmu_dir" + os.path.sep + "temp.zip " + self.targetDirPath + os.path.sep + "fmu_dir" + os.path.sep + "binaries" + os.path.sep + " -r " + self.targetDirPath + os.path.sep + "fmu_dir" + os.path.sep + "modelDescription.xml"
        os.system(zip_arc)
        shutil.copyfile(self.targetDirPath + os.path.sep + "fmu_dir" + os.path.sep + "temp.zip",
                        self.targetDir + os.path.sep + self.modelName + ".fmu")
        self.printMsg("Finish.")

    # *** Done with FMU generation ***

    def copyTemplateDirectory(self, templatePath):
        """Copies the FMI_template folder to the new location. Replaces the old name of directories, files
        and script in the files with the newly user defined name (i.e.modelName).

        Path to target directory is stored in self.targetDirPath.
        If target directory exists already, it is moved to trash first.

        Const-function, does not modify the state of the object.

        Arguments:

        templatePath -- The absolute path to the FMI_template directory.

        Example::

           self.copyTemplateDirectory("../data/FMI_template")
           # will rename "FMI_template" to "testFMU" after copying
        """

        try:
            # check if target directory exists already
            if os.path.exists(self.targetDirPath):
                shutil.rmtree(self.targetDirPath)

            # if parent directory does not yet exist, create it
            parentDir = os.path.dirname(self.targetDirPath)
            if not os.path.exists(parentDir):
                os.makedirs(parentDir)
            # Copy source folder to a new location(i.e. self.targetDirPath)
            shutil.copytree(templatePath, self.targetDirPath)
            # Set modified time of newly created folder
            os.utime(self.targetDirPath, None)
        except:
            raise RuntimeError("Cannot copy FMI_template directory to target directory")

        try:
            # rename files that must be named according as the modelName
            # os.rename(self.targetDirPath + "/" + self.tmpltFolderName + ".pro",
            #           self.targetDirPath + "/" + self.modelName + ".pro")
            os.rename(self.targetDirPath + "/src/" + self.tmpltFolderName + ".cpp",
                      self.targetDirPath + "/src/" + self.modelName + ".cpp")
            os.rename(self.targetDirPath + "/src/" + self.tmpltFolderName + ".h",
                      self.targetDirPath + "/src/" + self.modelName + ".h")
        except:
            raise RuntimeError("Cannot rename FMI_template files")

    def substitutePlaceholders(self):
        """Processes all FMI_template files and replaces placeholders within the files with generated values.

        1. It generates a globally unique identifier.
        2. It generates a local time stamp.
        3. It replaces placeholders.

        """

        # Generate globally unique identifier
        guid = uuid.uuid1()

        # Generate time stamp of local date and time
        localTime = time.strftime('%Y-%m-%dT%I:%M:%SZ', time.localtime())

        # We process file after file

        # loop to walk through the new folder
        for root, dirs, files in os.walk(self.targetDirPath):
            # process all files
            for f in files:

                # compose full file path
                src = os.path.join(root, f)

                try:
                    # read file into memory, variable 'data'
                    if sys.version_info[0] < 3:
                        fobj = open(src, 'r')
                        data = fobj.read().decode('utf8')
                    else:
                        fobj = open(src, 'r', encoding='utf-8')
                        data = fobj.read()
                    fobj.close()
                except Exception as e:
                    self.printMsg(str(e))
                    raise RuntimeError("Error reading file: {}".format(src))

                # generic data adjustment
                data = data.replace(self.tmpltFolderName, self.modelName)

                # special handling for certain file types

                # 1. modelDescription.xml
                if f == "modelDescription.xml":
                    data = self.adjustModelDescription(data, localTime, guid)

                # 2. <modelName>.cpp
                if f == self.modelName + ".cpp":
                    data = self.adjustSourceCodeFiles(data, guid)

                # finally, write data back to file
                try:
                    if sys.version_info[0] < 3:
                        fobj = open(src, 'w')
                        fobj.write(data.encode("utf8"))
                    else:
                        fobj = open(src, 'w', encoding="utf-8")
                        fobj.write(data)
                    fobj.close()
                except Exception as e:
                    self.printMsg("Error writing file: {}".format(str(e)))
                    raise RuntimeError("Error writing file: {}".format(src))

    def adjustModelDescription(self, data, localTimeStamp, guid):
        """Adjusts content of `modelDescription.xml` file.
        Take the content of FMI_template file in argument data. Inserts strings for model name, description,
        date and time, GUID, ...

        Arguments:

        data -- string holding the contents of the modelDescription.xml file
        localTimeStamp -- time stamp of local time
        guid -- globally unique identifier

        Returns:

        Returns string with modified modelDescription.xml file
        """

        data = data.replace("$$dateandtime$$", localTimeStamp)
        data = data.replace("$$GUID$$", str(guid))
        data = data.replace("$$description$$", self.description)
        data = data.replace("$$modelName$$", self.modelName)

        # TODO : substitute remaining placeholders
        data = data.replace("$$version$$", "1.0.0")
        data = data.replace("$$author$$", "not specified")
        data = data.replace("$$copyright$$", "not specified")
        data = data.replace("$$license$$", "not specified")

        # generate scalar variable section

        VARIABLE_TEMPLATE = """
		<!-- Index of variable = "$$index$$" -->
		<ScalarVariable
			name="$$name$$"$$desc$$
			valueReference="$$valueRef$$"
			variability="$$variability$$"
			causality="$$causality$$"
			initial="$$initial$$">
			<$$typeID$$$$start$$$$unit$$/>
		</ScalarVariable>
		"""

        MODEL_STRUCTURE_TEMPLATE = """			<Unknown index="$$index$$" dependencies="$$dependlist$$"/>
		"""

        scalarVariableDefs = ""
        # now add all variables one by one
        idx = 0
        dependList = ""
        for var in self.variables:
            idx = idx + 1
            var.idx = idx
            varDefBlock = VARIABLE_TEMPLATE
            varDefBlock = varDefBlock.replace("$$index$$", str(idx))
            varDefBlock = varDefBlock.replace("$$name$$", var.name)

            if len(var.description) != 0:
                varDefBlock = varDefBlock.replace("$$desc$$", u'\n            description="{}"'.format(var.description))
            else:
                varDefBlock = varDefBlock.replace("$$desc$$", "")

            # generate value if auto-numbered
            assert (var.valueRef != -1)
            varDefBlock = varDefBlock.replace("$$valueRef$$", str(var.valueRef))

            if var.causality == "input":
                dependList = dependList + " " + str(idx)

            varDefBlock = varDefBlock.replace("$$variability$$", var.variability)
            varDefBlock = varDefBlock.replace("$$causality$$", var.causality)
            varDefBlock = varDefBlock.replace("$$initial$$", var.initial)

            varDefBlock = varDefBlock.replace("$$typeID$$", var.typeID)

            if var.typeID == 'Real' and len(var.unit) > 0:
                varDefBlock = varDefBlock.replace("$$unit$$", ' unit="{}"'.format(var.unit))
            else:
                varDefBlock = varDefBlock.replace("$$unit$$", "")

            if var.initial == "calculated":
                varDefBlock = varDefBlock.replace("$$start$$", "")
            else:
                varDefBlock = varDefBlock.replace("$$start$$", ' start="{}"'.format(var.startValue))

            scalarVariableDefs = scalarVariableDefs + "\n" + varDefBlock

        data = data.replace("$$scalarVariables$$", scalarVariableDefs)

        dependList = dependList.strip()

        # output dependency block
        modelStructureDefs = ""
        for var in self.variables:
            if var.causality == "output":
                dependsDef = MODEL_STRUCTURE_TEMPLATE
                dependsDef = dependsDef.replace("$$index$$", str(var.idx))
                dependsDef = dependsDef.replace("$$dependlist$$", dependList)
                modelStructureDefs = modelStructureDefs + "\n" + dependsDef

        data = data.replace("$$outputDependencies$$", modelStructureDefs)
        return data

    def adjustSourceCodeFiles(self, data, guid):
        """Adjusts content of `<modelName>.cpp` file.
        Replaces the following placeholders:

        - $$variables$$ - defines for each published variables
        - $$initialization$$ - start values for all input and output variables
        - $$initialStatesME$$ - initialization code for Model Exchange
        - $$initialStatesCS$$ - initialization code for Model Exchange
        - $$getInputVars$$ - retrieves input/parameter values for access in C++ code
        - $$setOutputVars$$ - sets calculated values for access in C++ code

        Arguments:

        data -- string holding the contents of the <modelName>.cpp file
        guid -- globally unique identifier

        Returns:

        Returns the modified string.

        """

        data = data.replace("$$GUID$$", str(guid))
        # generate variable defines
        s = ""
        input_number = 0
        output_number = 0
        for var in self.variables:
            # compose type prefix for cpp member variables
            typePrefix = ""
            cppType = ""
            if var.typeID == "Real":
                typePrefix = "real"
                cppType = "double"
            elif var.typeID == "Boolean":
                typePrefix = "bool"
                cppType = "bool"
            elif var.typeID == "Integer":
                typePrefix = "integer"
                cppType = "int"
            elif var.typeID == "String":
                typePrefix = "string"
                cppType = "const std::string &"
            assert (typePrefix)

            if var.causality == "input":
                input_number += 1
                sdef = "#define FMI_INPUT_{} {}".format(var.name, var.valueRef)
                s = s + sdef + "\n"
                var.varDefine = "FMI_INPUT_{}".format(var.name)
                var.cppVariable = "m_{}Var[{}]".format(typePrefix, var.varDefine)
                var.getStatement = "{} {} = {};".format(cppType, var.name, var.cppVariable)
            elif var.causality == "output":
                output_number += 1
                sdef = "#define FMI_OUTPUT_{} {}".format(var.name, var.valueRef)
                s = s + sdef + "\n"
                var.varDefine = "FMI_OUTPUT_{}".format(var.name)
                var.cppVariable = "m_{}Var[{}]".format(typePrefix, var.varDefine)
                if var.typeID == "String":
                    var.setStatement = '{} = ""; // TODO : store your results here'.format(var.cppVariable)
                else:
                    var.setStatement = "{} = 0; // TODO : store your results here".format(var.cppVariable)
            elif var.causality == "calculatedParameter":
                sdef = "#define FMI_PARA_{} {}".format(var.name, var.valueRef)
                s = s + sdef + "\n"
                var.varDefine = "FMI_PARA_{}".format(var.name)
                var.cppVariable = "m_{}Var[{}]".format(typePrefix, var.varDefine)
                if var.typeID == "String":
                    var.setStatement = '{} = ""; // TODO : store your results here'.format(var.cppVariable)
                else:
                    var.setStatement = "{} = 0; // TODO : store your results here".format(var.cppVariable)
            elif var.causality == "parameter":
                sdef = "#define FMI_PARA_{} {}".format(var.name, var.valueRef)
                s = s + sdef + "\n"
                var.varDefine = "FMI_PARA_{}".format(var.name)
                var.cppVariable = "m_{}Var[{}]".format(typePrefix, var.varDefine)
                var.getStatement = "{} {} = {};".format(cppType, var.name, var.cppVariable)
            elif var.causality == "local":
                sdef = "#define FMI_LOCAL_{} {}".format(var.name, var.valueRef)
                s = s + sdef + "\n"
                var.varDefine = "FMI_LOCAL_{}".format(var.name)
                var.cppVariable = "m_{}Var[{}]".format(typePrefix, var.varDefine)
                var.getStatement = "{} {} = {};".format(cppType, var.name, var.cppVariable)
            else:
                var.varDefine = ""  # variable will not be used in cpp code

        data = data.replace("$$variables$$", s)

        # generate initialization code
        sIn = ""
        for var in self.variables:
            if var.causality == "input" or var.causality == "parameter":
                if var.typeID == "String":
                    sdef = '\t{} = \"{}\";'.format(var.cppVariable, var.startValue)
                else:
                    # we expect start value to be an integer value, otherwise we default to 0
                    if len(var.startValue) == 0:
                        var.startValue = "0"
                    sdef = "\t{} = {};".format(var.cppVariable, var.startValue)
                sIn = sIn + sdef + "\n"
        if len(sIn) > 0:
            sIn = "\t// initialize input variables and/or parameters\n" + sIn + "\n"

        sOut = ""
        for var in self.variables:
            if var.causality == "output" or var.causality == "local":
                if var.typeID == "String":
                    sdef = '\t\t{} = \"{}\";'.format(var.cppVariable, var.startValue)
                else:
                    # we expect start value to be an integer value, otherwise we default to 0
                    if len(var.startValue) == 0:
                        var.startValue = "0"
                    sdef = "\t{} = {};".format(var.cppVariable, var.startValue)
                sOut = sOut + sdef + "\n"
        if len(sOut) > 0:
            sOut = "\t// initialize output variables\n" + sOut + "\n"

        data = data.replace("$$initialization$$", sIn + sOut)

        # todo states
        sendBufferSectionStr = ""
        recvBufferSectionStr = ""
        input_idx = 1
        output_idx = 1
        real_var_flag = 0
        bool_var_flag = 0
        int_var_flag = 0
        for var in self.variables:
            if var.causality == "input":
                if var.typeID == "Real":
                    real_var_flag = 1
                    sendBufferSectionStr += "\tsend_buffer[" + str(
                        input_idx - 1) + "] = (double)(real_var[FMI_INPUT_" + var.name + "]);\n"
                elif var.typeID == "Boolean":
                    bool_var_flag = 1
                    sendBufferSectionStr += "\tsend_buffer[" + str(
                        input_idx - 1) + "] = (double)(bool_var[FMI_INPUT_" + var.name + "]);\n"
                elif var.typeID == "Integer":
                    int_var_flag = 1
                    sendBufferSectionStr += "\tsend_buffer[" + str(
                        input_idx - 1) + "] = (double)(int_var[FMI_INPUT_" + var.name + "]);\n"
                input_idx += 1
            elif var.causality == "output":
                if var.typeID == "Real":
                    real_var_flag = 1
                    recvBufferSectionStr += "\t\tmemcpy(&temp, recv_buffer + " + str(
                        output_idx - 1) + " * sizeof(double), sizeof(double));\n\t\treal_var[FMI_OUTPUT_" + var.name + "] = (double)temp;\n\t\tstd::cout << \"" + var.name + "\" <<\": \"<< real_var[FMI_OUTPUT_" + var.name + "] << std::endl;\n"
                elif var.typeID == "Boolean":
                    bool_var_flag = 1
                    recvBufferSectionStr += "\t\tmemcpy(&temp, recv_buffer + " + str(
                        output_idx - 1) + " * sizeof(double), sizeof(double));\n\t\tbool_var[FMI_OUTPUT_" + var.name + "] = (bool)temp;\n\t\tstd::cout << \"" + var.name + "\" <<\": \"<< bool_var[FMI_OUTPUT_" + var.name + "] << std::endl;\n"
                elif var.typeID == "Integer":
                    int_var_flag = 1
                    recvBufferSectionStr += "\t\tmemcpy(&temp, recv_buffer + " + str(
                        output_idx - 1) + " * sizeof(double), sizeof(double));\n\t\tint_var[FMI_OUTPUT_" + var.name + "] = (int)temp;\n\t\tstd::cout << \"" + var.name + "\" <<\": \"<< int_var[FMI_OUTPUT_" + var.name + "] << std::endl;\n"
                output_idx += 1
        funcArgsStr = ""
        funcArgs2Str = ""
        if real_var_flag == 1:
            funcArgsStr += "std::map<int, double>& real_var, "
            funcArgs2Str += "m_realVar, "
        if bool_var_flag == 1:
            funcArgsStr += "std::map<int, int>& bool_var, "
            funcArgs2Str += "m_boolVar, "
        if int_var_flag == 1:
            funcArgsStr += "std::map<int, int>& int_var, "
            funcArgs2Str += "m_integerVar, "
        funcArgsStr = funcArgsStr.rstrip(', ')
        funcArgs2Str = funcArgs2Str.rstrip(', ')
        data = data.replace("$$funcArgs$$", funcArgsStr)
        data = data.replace("$$funcArgs2$$", funcArgs2Str)
        data = data.replace("$$sendBufferSection$$", sendBufferSectionStr)
        data = data.replace("$$recvBufferSection$$", recvBufferSectionStr)
        data = data.replace("$$input_number$$", str(input_number))
        data = data.replace("$$output_number$$", str(output_number))
        data = data.replace("$$initialStatesME$$", "")
        data = data.replace("$$initialStatesCS$$", "")
        data = data.replace("$$modelName$$", self.modelName)

        # compose getter block
        s = ""
        for var in self.variables:
            if var.causality == "input" or var.causality == "parameter" or var.causality == "local":
                sdef = "\t" + var.getStatement
                s = s + sdef + "\n"
        data = data.replace("$$getInputVars$$", s)

        # compose setter block
        s = ""
        for var in self.variables:
            if var.causality == "output" or var.causality == "calculatedParameter":
                sdef = "\t" + var.setStatement
                s = s + "//" + sdef + "\n"
        data = data.replace("$$setOutputVars$$", s)

        return data

    def writeInputData(self, targetFile):

        varArray = []

        for v in self.variables:
            varArray.append(v.toJson())

        data = {
            "modelName": self.modelName,
            "description": self.description,
            "variables": varArray
        }

        # if parent directory does not yet exist, create it
        parentDir = os.path.dirname(targetFile)
        parentDir = os.path.abspath(parentDir)
        if not os.path.exists(parentDir):
            os.makedirs(parentDir)

        with open(targetFile, 'w') as outfile:
            json.dump(data, outfile, indent=4)

    def readInputData(self, targetFile):
        with open(targetFile, 'r') as f:
            data = json.load(f)
            self.description = data['description']
            for a in data['variables']:
                v = varDefFromJson(a)
                self.variables.append(v)

    def generateAddrConfig(self):
        with open(self.targetDir + os.path.sep + "addr.config", "w") as f:
            f.writelines(
                [self.modelName + "_local_port=12000\n", self.modelName + "_remote_ip=127.0.0.1\n",
                 self.modelName + "_remote_port=5500"])
