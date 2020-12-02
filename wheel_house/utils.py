import jsonc
import json
import yaml
import os
import tempfile
import tarfile
import requests
import uuid

def get_json(obj):
    if type(obj) == dict:
        return obj
    else:
        return obj.to_json()

def get_from_key_list(data, keys):
    if not keys:
        return data
    # if the key doesn't exist then return None
    if not keys[0] in data.keys():
        return None
    if len(keys) > 1:
        # if we aren't at the last key then go a level deeper
        return get_from_key_list(data[keys[0]], keys[1:])
    else:
        # return the value we want
        return data[keys[0]]

def set_from_key_list(data, keys, value):
    # if the key doesn't exist then return None
    if not keys[0] in data.keys():
        if len(keys) == 1:
            data[keys[0]] = value
            return data
        else:
            return None
        return None
    if len(keys) > 1:
        # if we aren't at the last key then go a level deeper
        ret = set_from_key_list(data[keys[0]], keys[1:], value)
        if ret == None:
            return None
        else:
            data[keys[0]] = ret
    else:
        # return the value we want
        data[keys[0]] = value
    return data

def add_in_values(data, values):
    for k in values:
        if values[k] != None:
            keys = k.split('.')
            data = set_from_key_list(data, keys, values[k])
    return data

def stringify(obj):
    name = type(obj).__name__
    variables = vars(obj)
    str_rep = ''
    for v in variables:
        str_rep += '{}={}, '.format(v, getattr(obj, v))
    return name + '(' + str_rep[:-2] + ')'

def clean_null(d):
    clean = {}
    if type(d) == dict:
        for k, v in d.items():
            if type(v) == dict:
                nested = clean_null(v)
                if len(nested.keys()) > 0:
                    clean[k] = nested
            elif type(v) == list:
                for i in range(0, len(v)):
                    v[i] = clean_null(v[i])
                v = [i for i in v if i]
                if len(v) > 0:
                    clean[k] = v
            elif v:
                clean[k] = v
            for k in clean:
                if clean[k] == {} or clean[k] == []:
                    del clean[k]
    else:
        clean = d
    return clean

def clean_unset(data):
    if type(data) == dict:
        for k in data:
            if type(data[k]) == dict:
                data[k] = clean_unset(data[k])
            elif type(data[k]) == list:
                data[k] = clean_unset(data[k])
            elif type(data[k]) == str:
                if data[k].startswith('<') and data[k].endswith('>'):
                    data[k] = None
    else:
        for k in range(0, len(data)):
            if type(data[k]) == dict:
                data[k] = clean_unset(data[k])
            elif type(data[k]) == list:
                data[k] = clean_unset(data[k])
            elif type(data[k]) == str:
                if data[k].startswith('<') and data[k].endswith('>'):
                    data[k] = None
    return data

def recurse_expand(data, components_list, indent=0):
    # print(' ' * indent + str(data))
    if type(data) == dict:
        for k in data:
            if type(data[k]).__name__ in components_list:
                data[k] = data[k].to_json()
            else:
                if type(data[k]) == dict:
                    data[k] = recurse_expand(data[k], components_list, indent = indent+2)
                elif type(data[k]) == list:
                    data[k] = recurse_expand(data[k], components_list, indent = indent+2)
                elif type(data[k]) == str:
                    if data[k].startswith('<') and data[k].endswith('>'):
                        data[k] = None
    else:
        for k in range(0, len(data)):
            if type(data[k]).__name__ in components_list:
                data[k] = data[k].to_json()
            else:
                if type(data[k]) == dict:
                    data[k] = recurse_expand(data[k], components_list, indent = indent+2)
                elif type(data[k]) == list:
                    data[k] = recurse_expand(data[k], components_list, indent = indent+2)
                elif type(data[k]) == str:
                    if data[k].startswith('<') and data[k].endswith('>'):
                        data[k] = None
    return data

def recurse_build(data, key_list, elements, indent=0):
    # print(' ' * indent + str(data))
    if type(data) == dict:
        for k in data:
            key = '.'.join(key_list + [k])
            if key in elements.keys():
                data[k] = elements[key]
            else:
                if type(data[k]) == dict:
                    data[k] = recurse_build(data[k], key_list + [k], elements, indent = indent+2)
                elif type(data[k]) == list:
                    data[k] = recurse_build(data[k], key_list + [k], elements, indent = indent+2)
    else:
        for k in range(0, len(data)):
            key = '.'.join(key_list)
            if key in elements.keys():
                data[k] = elements[key]
            else:
                if type(data[k]) == dict:
                    data[k] = recurse_build(data[k], key_list, elements, indent = indent+2)
                elif type(data[k]) == list:
                    data[k] = recurse_build(data[k], key_list, elements, indent = indent+2)
    return data

def get_key_string(data):
    temp = list(get_paths(data))
    ret = ['.'.join(a) for i, a in enumerate(temp) if a not in temp[:i]]
    return ret

def get_paths(d, current = []):
    for a, b in d.items():
        yield current+[a]
        if isinstance(b, dict):
            yield from get_paths(b, current+[a])
        elif isinstance(b, list):
            for i in b:
                yield from get_paths(i, current+[a])

def replace_refs(data, pattern, config_data):
    refs = []
    if type(data) == jsonc.JSONCDict or type(data) == dict:
        for k in data:
            if type(data[k]) == dict:
                refs += replace_refs(data[k], pattern, config_data)
            elif type(data[k]) == list:
                refs += replace_refs(data[k], pattern, config_data)
            elif type(data[k]) == str:
                res = [(r[2:-1].split('.')[0], r[2:-1].split('.')[1:]) for r in pattern.findall(data[k])]
                if len(res) > 0:
                    data[k] = handle_ref(config_data, res[0][1])
    elif type(data) == list:
        for k in range(0, len(data)):
            if type(data[k]) == dict:
                refs += replace_refs(data[k], pattern, config_data)
            elif type(data[k]) == list:
                refs += replace_refs(data[k], pattern, config_data)
            elif type(data[k]) == str:
                res = [(r[2:-1].split('.')[0], r[2:-1].split('.')[1:]) for r in pattern.findall(data[k])]
                if len(res) > 0:
                    data[k] = handle_ref(config_data, res[0][1])
    elif type(data) == str:
        res = [(r[2:-1].split('.')[0], r[2:-1].split('.')[1:]) for r in pattern.findall(data)]
        if len(res) > 0:
            data = handle_ref(config_data, res[0][1])
    return data

def handle_ref(config_data, ref_path):
    out = get_from_key_list(config_data, ref_path)
    return out

def format_replacement(data):
    out = []
    if type(data) == dict or type(data) == list:
        return json.dumps(data, indent=4)
    elif type(data) == str:
        return '"{}"'.format(data)
    else:
        return str(data)

def read_file(path):
    if path.endswith('.yaml') or path.endswith('.yml'):
        with open(path) as f:
            data = yaml.safe_load(f)
    elif path.endswith('.json'):
        with open(path) as f:
            try:
                data = jsonload(f)
            except:
                data = jsonc.load(f)
    elif path.endswith('.jsonc'):
        with open(path) as f:
            data = jsonc.load(f)
    return data

def read_data(path, data):
    if path.endswith('.yaml') or path.endswith('.yml'):
        data = yaml.safe_load(data)
    elif path.endswith('.json'):
        try:
            data = json.loads(data)
        except:
            data = jsonc.loads(data)
    elif path.endswith('.jsonc'):
        data = jsonc.loads(data)
    return data

def find_template(base, obj_type):
    files = os.listdir(os.path.join(base, obj_type))
    if 'template.yaml' in files:
        return os.path.join(base, obj_type, 'template.yaml')
    if 'template.yml' in files:
        return os.path.join(base, obj_type, 'template.yml')
    if 'template.json' in files:
        return os.path.join(base, obj_type, 'template.json')
    if 'template.jsonc' in files:
        return os.path.join(base, obj_type, 'template.jsonc')
    err = ValueError('No template file found for object type {}'.format(obj_type))
    raise err

def download_compass(url, name, version):
    temp_path = tempfile.mkdtemp()
    uuid_name = str(uuid.uuid1())

    path = temp_path + '/' + uuid_name

    r = requests.get(url + '/api/getCompassURLByNameAndVersion/' + name + '/' + version, allow_redirects=True)
    data = json.loads(r.content)
    compass_url = data['url']
    r = requests.get(compass_url, allow_redirects=True)
    open(path, 'wb').write(r.content)

    return path, temp_path

def list_compassess(url, name):
    r = requests.get(url + '/api/getCompassObjectsByName/' + name, allow_redirects=True)
    data = json.loads(r.content)

    print('Compass Matches')
    print()
    header = '{:32s} {:32s}'.format('Name', 'Version')
    print(header)
    print('{0}-{1}'.format(32 * '-', 32 * '-'))
    for d in data['compasses']:
        line = '{:32s} {:32s}'.format(d['name'], d['version'])
        print(line)

def search_compassess(url, name):
    r = requests.get(url + '/api/getCompassObjectsByFuzzyName/' + name, allow_redirects=True)
    data = json.loads(r.content)

    print('Compass Fuzzy Matches')
    print()
    header = '{:32s}'.format('Name')
    print(header)
    print('{0}'.format(32 * '-'))
    for d in data['matches']:
        line = '{:32s}'.format(d)
        print(line)
    

def untar_compass(path, temp_path=None):
    if not temp_path:
        temp_path = tempfile.mkdtemp()

    tar = tarfile.open(path)
    tar.extractall(temp_path)
    tar.close()

    return temp_path