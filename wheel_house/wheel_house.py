import jsonc
import re
from collections import namedtuple
import yaml
import utils
import json
import enums
from k8sgen.builder import K8sBuilder
from aphelper import core
import os
import copy
from interactive import Interactive
import shutil

# define global variables
MatchObject = namedtuple("MatchObject", ["start", "end", "groups"])
INFO_PREFIX  = "[ INFO  ] :: "
DEBUG_PREFIX = "[ DEBUG ] :: "
WARN_PREFIX  = "[ WARN  ] :: "
ERROR_PREFIX = "[ ERROR ] :: "

FRONTEND_API = "http://localhost:8091"

class WheelHouse:

    def get_matches(self, pattern, text):
        """
        Get all matches from a regex search and create a list of named tuples
        containing the start and end character positions
        along with the match contents
        """
        matches = []
        for m in pattern.finditer(text):
            matches.append(MatchObject(start=m.start(), end=m.end(), groups=m.groups()))
        return matches

    def check_for_loops(self, obj, config_data, obj_type, compass_path, contents=None):
        """
        Check for blocks of template files of the form
        <inline comment marker> {% for <variable> in <config section> %}
            <arbitatry contents>
        <inline comment marker> {% end for %}

        If any are found, then the contents within the block are repeated according
        to the loop
        """
        # if we haven't passed the template file contents then
        # we need to read in the template file
        if not contents:
            template_file = utils.find_template(os.path.join(compass_path, 'templates'), obj_type)
            with open(template_file) as f:
                contents = f.read()

        # define regex patterns
        begin_for_pattern = re.compile('(?:\/\/|#|;)\s*\{\%\s*for\s*(\S*)\s*in\s*(\S*)\s*\%\}')
        end_for_pattern = re.compile('(?:\/\/|#|;)\s*\{\%\s*end\s*for\s*\%\}')

        # get matches for each of the patterns
        begin_for_matches = self.get_matches(begin_for_pattern, contents)
        end_for_matches = self.get_matches(end_for_pattern, contents)

        out = ''
        
        # check to make sure that for every for loop beginning we have an end
        if len(begin_for_matches) != len(end_for_matches):
            if self.LOG_LEVEL >= enums.LogLevel.ERROR.value:
                print('{}Found {} beginning loop statements and {} ending loop statments'.format(ERROR_PREFIX, len(begin_for_matches), len(end_for_matches)))
            err = ValueError('For loop statement count mismatch')
            raise err

        out_contents = ''
        prev_index = 0
        if self.LOG_LEVEL >= enums.LogLevel.DEBUG.value:
            print('{}Found {} for loop blocks'.format(DEBUG_PREFIX, len(begin_for_matches)))

        # loop through the matches
        for i in range(0, len(begin_for_matches)):
            # add the contents between loops to the final output file
            out_contents += contents[prev_index:begin_for_matches[i].start]
            prev_index = end_for_matches[i].end
            # get the block to be repeated
            repeat_contents = contents[begin_for_matches[i].end:end_for_matches[i].start]
            repeat_contents = repeat_contents.strip()

            # figure out what variable the user wants to use
            var_name = begin_for_matches[i].groups[0]
            # figure out where in the config document they want to loop
            config_loc = begin_for_matches[i].groups[1]
            config_objs = utils.get_from_key_list(config_data, config_loc.split('.')[1:])

            # loop through the config location
            for variable in config_objs:
                variable_name = list(variable.keys())[0]
                variable_data = variable[variable_name]
                # define special variables that can be accessed
                special_refs = {
                    '__name__': variable_name
                }
                repeat_copy = repeat_contents
                # replace any variable references in the repeat block
                for ref in special_refs:
                    repeat_copy = re.sub('\$\{\s*' + var_name + '\.' + ref + '\s*}', special_refs[ref], repeat_copy)
                elements = re.findall('\$\{' + var_name + '\.(\S*)\}', repeat_copy)
                for el in elements:
                    item = utils.format_replacement(utils.get_from_key_list(variable_data, el.split('.')))
                    repeat_copy = re.sub('"\$\{' + var_name + '\.' + el + '}"', item, repeat_copy)
                # add the processed repeat block to the output contents
                out_contents += repeat_copy + '\n'

        out_contents += contents[prev_index:]
        # remove invalid commas
        out_contents = re.sub(',\n\s*\}', '\n}', out_contents)
        out_contents = re.sub(',\n\s*\]', '\n]', out_contents)

        return out_contents

    def check_for_conditionals(self, obj, config_data, obj_type, compass_path, contents=None):
        """
        Check for blocks of template files of the form
        <inline comment marker> {% if <left> <operator> <right> %}
            <arbitatry contents>
        <inline comment marker> {% end if %}

        If any are found, then the contents within the block are kept in
        if they meet the confidition defined
        """
        # if we haven't passed the template file contents then
        # we need to read in the template file
        if not contents:
            template_file = utils.find_template(os.path.join(compass_path, 'templates'), obj_type)
            with open(template_file) as f:
                contents = f.read()

        # define regex patterns
        begin_if_pattern = re.compile('(?:\/\/|#|;)\s*\{\%\s*if\s*(\S*)\s*(\S*)\s*(\S*)\s*\%\}')
        end_if_pattern = re.compile('(?:\/\/|#|;)\s*\{\%\s*end\s*if\s*\%\}')

        # get matches for each of the patterns
        begin_if_matches = self.get_matches(begin_if_pattern, contents)
        end_if_matches = self.get_matches(end_if_pattern, contents)

        out = ''
        
        # check to make sure that for every for loop beginning we have an end
        if len(begin_if_matches) != len(end_if_matches):
            if self.LOG_LEVEL >= enums.LogLevel.ERROR.value:
                print('{}Found {} beginning conditional statements and {} ending conditional statments'.format(ERROR_PREFIX, len(begin_if_matches), len(end_if_matches)))
            err = ValueError('Conditional statement count mismatch')
            raise err

        out_contents = ''
        prev_index = 0
        if self.LOG_LEVEL >= enums.LogLevel.DEBUG.value:
            print('{}Found {} conditional blocks'.format(DEBUG_PREFIX, len(begin_if_matches)))

        # loop through the matches
        for i in range(0, len(begin_if_matches)):
            # add the contents between loops to the final output file
            out_contents += contents[prev_index:begin_if_matches[i].start]
            prev_index = end_if_matches[i].end
            # get the block to be conditionally evaluated
            if_contents = contents[begin_if_matches[i].end:end_if_matches[i].start]
            if_contents = if_contents.strip()

            # get the parts of the if statement
            left = begin_if_matches[i].groups[0].strip()
            operator = enums.Operators(begin_if_matches[i].groups[1].strip())
            right = begin_if_matches[i].groups[2].strip()

            # figure out the type of the left part of the statement
            if (left.startswith('"') and left.endswith('"')) or (left.startswith("'") and left.endswith("'")):
                left = left[1:-1]
            elif left.replace('.', '', 1).isdigit():
                left = float(left)
            elif left.endswith('.__keys__'):
                left = list(utils.get_from_key_list(config_data, left.split('.')[1:-1]).keys())
            else:
                left = utils.get_from_key_list(config_data, left.split('.')[1:])

            # figure out the type of the right side of the statement
            if (right.startswith('"') and right.endswith('"')) or (right.startswith("'") and right.endswith("'")):
                right = right[1:-1]
            elif right.replace('.', '', 1).isdigit():
                right = float(right)
            elif right.endswith('.__keys__'):
                right = list(utils.get_from_key_list(config_data, right.split('.')[1:-1]).keys())
            else:
                right = utils.get_from_key_list(config_data, right.split('.')[1:])

            # perform the operation depending on the operator
            if_result = False
            if operator == enums.Operators.IN:
                if_result = (left in right)
            elif operator == enums.Operators.EQUAL:
                if_result = (left == right)
            elif operator == enums.Operators.NOT_EQUAL:
                if_result = (left != right)
            elif operator == enums.Operators.LESS_THAN:
                if_result = (left < right)
            elif operator == enums.Operators.GREATER_THAN:
                if_result = (left > right)
            elif operator == enums.Operators.LESS_THAN_EQUAL:
                if_result = (left < right)
            elif operator == enums.Operators.GREATER_THAN_EQUAL:
                if_result = (left < right)

            # if the statement evaluated to true, then add it to the output
            if if_result:
                out_contents += if_contents + '\n'

        out_contents += contents[prev_index:]
        # remove invalid commas
        out_contents = re.sub(',\n\s*\}', '\n}', out_contents)
        out_contents = re.sub(',\n\s*\]', '\n]', out_contents)

        return out_contents

    def handle_variables(self, config, user_in):
        variable_pattern = '\$\{var\.(.*)\|(.*)\}'
        config = re.sub(variable_pattern, lambda m: user_in.get(m.groups()[0]) if m.groups()[0] in user_in.keys() else m.groups()[1], config)
        return config

    def build_obj(self, config_data, obj, obj_data, obj_type, compass_path, list_element=None):
        # create the __this__ key in the config
        if list_element != None:
            name = list(list_element.keys())[0]
            obj_data['__this__'] = list_element[name]
            obj_data['__this__']['__name__'] = name
        # check for template types
        contents = self.check_for_conditionals(obj, obj_data, obj_type, compass_path)
        contents = self.check_for_loops(obj, obj_data, obj_type, compass_path, contents=contents)
        out_data = json.loads(contents)

        # write out the intermediate jsonc file if debug is specified
        if self.LOG_LEVEL >= enums.LogLevel.DEBUG.value:
            print("{}Writing out debug file at debug/{}-{}.jsonc".format(DEBUG_PREFIX, obj, obj_type))
            with open('debug/{}-{}.jsonc'.format(obj, obj_type), 'w') as f:
                json.dump(out_data, f, indent=4)

        # write out the manifest
        out = self.builder.build_manifest(definition=out_data, config=obj_data)
        with open('out/{}-{}.yaml'.format(obj, obj_type), 'w') as f:
            f.write(out.to_yaml())
            
    def compose(self, compass_path, config_path, user_in, log_level):
        """
        Run the composition and create the manifest files
        """
        # get the config data
        with open(config_path) as f:
            config = f.read()
        if user_in:
            config = self.handle_variables(config, user_in)

        config_data = utils.read_data(config_path, config)
            
        # create the builder object
        self.builder = K8sBuilder()
        

        if log_level == 'NONE':
            self.LOG_LEVEL = enums.LogLevel.NONE.value
        elif log_level == 'ERROR':
            self.LOG_LEVEL = enums.LogLevel.ERROR.value
        elif log_level == 'INFO':
            self.LOG_LEVEL = enums.LogLevel.INFO.value
        elif log_level == 'WARN':
            self.LOG_LEVEL = enums.LogLevel.WARN.value
        elif log_level == 'DEBUG':
            self.LOG_LEVEL = enums.LogLevel.DEBUG.value

        if self.LOG_LEVEL >= enums.LogLevel.INFO.value:
            print('{}Composing manifests from configuration file: {}'.format(INFO_PREFIX, config_path))
        if self.LOG_LEVEL >= enums.LogLevel.DEBUG.value:
            if not os.path.exists('debug'):
                os.mkdir('debug')

        # loop through the objects to be built
        for obj_dict in config_data['objects']:
            obj = list(obj_dict.keys())[0]
            if self.LOG_LEVEL >= enums.LogLevel.INFO.value:
                print("{}Processing compositions for {}".format(INFO_PREFIX, obj))
            # loop through each component that is specified
            for obj_type in obj_dict[obj]:
                if obj_type.startswith('__'):
                    continue
                if self.LOG_LEVEL >= enums.LogLevel.DEBUG.value:
                    print("{}Composing object {}.{}".format(DEBUG_PREFIX, obj, obj_type))
                if type(obj_dict[obj][obj_type]) == list:
                    for el in obj_dict[obj][obj_type]:
                        self.build_obj(copy.deepcopy(config_data), obj, copy.deepcopy(obj_dict[obj]), obj_type, compass_path, list_element=el)
                else:
                    self.build_obj(copy.deepcopy(config_data), obj, copy.deepcopy(obj_dict[obj]), obj_type, compass_path)

    def install(self, args):
        """ 
        Grab a Compass package and perform the manifest creation 
        """
        if os.path.exists('out'):
            shutil.rmtree('out')
        os.mkdir('out')
        
        if args.uncompressed:
            compass_path = args.name
        else:
            if not args.local:
                path, temp_path = utils.download_compass(FRONTEND_API, args.name, args.version)
            else:
                path = args.name
                temp_path = None
            compass_path = utils.untar_compass(path, temp_path)

        files = os.listdir(compass_path)

        # check for config and interactive file
        for fi in files:
            if fi.startswith('config'):
                config_path = compass_path + '/' + fi
            elif fi.startswith('interactive'):
                interactive_path = compass_path + '/' + fi

        if not config_path:
            if self.LOG_LEVEL >= enums.LogLevel.ERROR.value:
                print('{}No configuration file found in {}'.format(ERROR_PREFIX, compass_path))
            exit(1)
        if interactive_path:
            interact = Interactive(interactive_path)
            user_in = interact.do_prompt()
        else:
            user_in = None

        self.compose(compass_path, config_path, user_in, args.log_level)

        if temp_path:
            shutil.rmtree(temp_path)

    def list_compasses(self, args):
        """
        List all versions available for a given compass name
        """
        utils.list_compassess(FRONTEND_API, args.name)

    def search_compasses(self, args):
        """
        List all versions available for a given compass name
        """
        utils.search_compassess(FRONTEND_API, args.name)

    def __init__(self):
        """ 
        Create the Wheel House parser and get the arguments passed 
        """
        ah = core.ArgparseHelper(def_file='data/parser.jsonc', parent=self)
        ah.execute()

if __name__ == '__main__':
    WheelHouse()
