import re
import copy
from collections import OrderedDict

from yaml_patch import ProcessLoader
import yaml
from yaml import MarkedYAMLError


class CreatorType:
    NO_CHECK = object()
    def __init__(self, creator=None, fields=None, init_kwargs=None, subclasses=None, inherit=None):
        self.creator = creator
        self.fields = fields or []
        self.fields = list(self.fields) if not isinstance(self.fields, str) else fields.split(' ')
            
        if self.creator:
            if isinstance(self.creator, str):
                self._typename = creator
                self.creator = self.make_creator(typename=creator)
        
        self.init_kwargs = init_kwargs or OrderedDict()
        self.subclasses = subclasses
        self.inherit = inherit
        if self.inherit:
            self.fields = self.inherit.fields + self.fields
            _init_kwargs = copy.deepcopy(self.inherit.init_kwargs)
            _init_kwargs.update(self.init_kwargs)
            self.init_kwargs = _init_kwargs
    
    
        
    def make_creator(self, typename):
        def object_creator(maker, *args, **kwargs):
            object = OrderedDict(kwargs)
            for key, arg in zip(self.fields, args):
                object[key] = arg
            object['type'] = typename
            if maker:
                maker.add(object)
            return object
        return object_creator
        
        
class Builder:
    from yaml.representer import Representer
    from yaml.constructor import Constructor
    yaml_representer = Representer()
    yaml_constructor = Constructor()
        
    def __init__(self, creator_type, k_pattern, k_belong, **kwargs):
        self.creator_type = creator_type
        self.k_pattern = k_pattern
        self.k_belong = k_belong
        self.ksub_cls = kwargs.get('ksub_cls', None)
        self.ksub_belong = kwargs.get('ksub_belong', None)
        self.extra_attribs = kwargs.get('extra_attribs', OrderedDict())
    
    @classmethod
    def _wrap_to_node(cls, obj, ref=None):
        wrap, repersent = cls._wrap_to_node, cls.yaml_representer.represent_data
        if not isinstance(obj, yaml.Node):
            _obj = obj
            if isinstance(obj, (list, tuple)):
                obj = repersent([])
                obj.value = list(_obj)
            elif isinstance(obj, dict):
                obj = repersent({})
                obj.value = list(_obj.items())        
            else:
                obj = repersent(_obj)
            
        if ref and not obj.start_mark:
            obj.start_mark, obj.end_mark = ref.start_mark, ref.end_mark
        
        if isinstance(obj, yaml.SequenceNode):
            obj.value = [wrap(v, obj) for v in obj.value]
        elif isinstance(obj, yaml.MappingNode):
            obj.value = [(wrap(k, obj), wrap(v, obj)) for k, v in obj.value]
        
        return obj
        
    @classmethod
    def _unwrap_from_node(cls, node):
        if isinstance(node, yaml.Node):
            return cls.yaml_constructor.construct_object(node)
        return node
        
    @classmethod
    def _offset_mark(cls, mark, offset):
        mark = copy.deepcopy(mark)
        mark.column += offset
        mark.pointer += offset
        return mark
        
    def major_match(self, key):
        assert isinstance(text, yaml.ScalarNode)
        if not key.value.startswith(self.k_pattern):
            return None, None
        
        subtypes_pos = len(self.k_pattern)
        _end_pos = len(key.value)
        ksubs_pos = _end_pos
        if self.ksub_escape:
            ksubs_pos = key.value.find(self.ksub_escape)
            if ksubs_pos == -1:
                ksubs_pos = _end_pos
                
        key_subtypes = copy.copy(key)
        key_subtypes.value = key.value[subtypes_pos:ksubs_pos]
        key_subtypes.start_mark = self._offset_mark(key.start_mark, subtypes_pos)
        
        key_ksubs = None
        if ksubs_pos != _end_pos:
            key_ksubs = copy.copy(key)
            key_ksubs.value = key.value[ksubs_pos:]
            key_ksubs.start_mark = self._offset_mark(key.start_mark, ksubs_pos)
            
        return key_subtypes, key_ksubs
        
    def subtype_match(self, key_subtypes):
        # let title decide which class to create
        # and decide defualt kwargs
        if self.creator_type.subclasses is not None:
            creator_type, _kwlist = self.text_match(key_subtypes, self.creator_type.subclasses)
            if creator_type:
                values.value.extend(_kwlist)
            else:
                raise MarkedYAMLError(None, None, '找不到可符合的類別', key_text.start_mark)
        else:
            creator_type = self.creator_type
        return creator_type, _kwlist

        
    @classmethod
    def text_match(cls, text, classmap):
        assert isinstance(text, yaml.ScalarNode)
        _cls = kwargs_list =  None
        for regex, match_cls in classmap.items():
            m = re.compile(regex).match(text.value)
            if m:
                _cls = match_cls
                kwargs_list = [cls._wrap_to_node({_k:_v}, text) for _k, _v in m.groupdict().items()]
                break
        return _cls, kwargs_list
    
    def build_ksub(self, maker, key_text, init_kwargs):
        ref_node = key_text
        
        assert isinstance(self.ksub_cls, OrderedDict)
        _cls, _kwlist = self.text_match(key_text, self.ksub_cls)
        if _cls:
            sub = self.common_build(maker, _cls, key_text, self._wrap_to_node(_kwlist, ref_node))
            init_kwargs.setdefault(self.ksub_belong, []).append(sub)
    
    def _from_kvlist(self, maker, key, values, parent_kwargs):
        if not key.value.startswith(self.k_pattern):
            return False

        assert isinstance(parent_kwargs, OrderedDict)
        assert isinstance(values, yaml.SequenceNode)
        
        key_text = copy.copy(key)
        key_text.value = key.value[len(self.k_pattern):]
        key_text.start_mark = self._offset_mark(key.start_mark, len(self.k_pattern))
        # let title decide which class to create
        # and decide defualt kwargs
        if self.creator_type.subclasses is not None:
            creator_type, _kwlist = self.text_match(key_text, self.creator_type.subclasses)
            if creator_type:
                values.value.extend(_kwlist)
            else:
                raise MarkedYAMLError(None, None, '找不到可符合的類別', key_text.start_mark)
        else:
            creator_type = self.creator_type
            
        init_kwargs = copy.deepcopy(self.extra_attribs)
        assert isinstance(init_kwargs, OrderedDict)
        if self.ksub_cls:
            self.build_ksub(maker, key_text, init_kwargs)
        object = self.common_build(maker, creator_type, key_text, values, init_kwargs)
        parent_kwargs.setdefault(self.k_belong, []).append(object)
        return True
        
        
    @classmethod
    def from_kvlist(cls, maker, key, values, parent_kwargs):
        values = values or cls._wrap_to_node([], key)
        for builder in maker.builder_list:
            if builder._from_kvlist(maker, key, values, parent_kwargs):
                return True
        return False
    
    @classmethod
    def common_build(cls, maker, creator_type, name, kwlist, init_kwargs=None):
        args = []
        build_kwargs = copy.deepcopy(creator_type.init_kwargs)
        build_kwargs.update(init_kwargs or {})
        objk_dict = {}
        for v in kwlist.value:
            if isinstance(v, yaml.MappingNode):
                objk, objv = v.value[0]
                objk.value = maker.translate_attr_table.get(objk.value, objk.value)
                # objk, objv is constructor
                if cls.from_kvlist(maker, objk, objv, build_kwargs):
                    continue
                # objk, objv is attributes
                attr = cls._unwrap_from_node(objk)
                #if attr not in creator_type.fields:
                #    raise MarkedYAMLError(None, None, '類別沒有這個屬性', objk.start_mark)
                build_kwargs[attr] = cls._unwrap_from_node(objv)
                objk_dict[attr] = objk
            else:
                if isinstance(v, yaml.ScalarNode):
                    if cls.from_kvlist(maker, v, None, build_kwargs):
                        # element v is constructor
                        continue
                # element v is fixed-position attributes, maybe is array
                args.append(v)
        
        # check args and kwargs of creation
        extra = list(creator_type.fields)
        for attr in build_kwargs.keys():
            # TODO: 先檢查extra在比較前面的項目
            if not(extra and extra[0] == creator_type.NO_CHECK):
                if attr not in extra:
                    if attr in objk_dict:
                        raise MarkedYAMLError(None, None, '多餘的條目: {0}'.format(attr), objk_dict[attr].start_mark)
                    else:
                        raise MarkedYAMLError(None, None, '多餘的預設條目: {0}'.format(attr), kwlist.start_mark)
                extra.remove(attr)
        if 'name' in extra:
            args = [name] + args
        for arg in args:
            if len(extra) == 0:
                raise MarkedYAMLError(None, None, '多餘的條目', arg.start_mark)
            if extra[0] != creator_type.NO_CHECK:
                extra.pop(0)
        
        if len(extra) > 0:
            if extra[0] != creator_type.NO_CHECK:
                raise MarkedYAMLError(None, None, '還有未指定的屬性: {}'.format(extra[0]), kwlist.start_mark)
        
        
        build_args = [cls._unwrap_from_node(arg) for arg in args]
        object = creator_type.creator(maker, *build_args, **build_kwargs)
        return object

class InstCreatorType(CreatorType):
    def make_creator(self, typename):
        argument_re = re.compile(r'(?:,\s*([a-z]+)(\:[a-z]+)?(\=[a-z]+)?\s*)')
        name_re = re.compile(r'([A-Za-z0-9]+)\(([^\)]+)?\)')
        vm_getProp_re = re.compile(r'\&([A-Za-z0-9]+)')
        vm_getPropRef_re = re.compile(r'\&\*([A-Za-z0-9]+)')
        
        def object_creator(maker, *args, **kwargs):
            name, *scripts = args
            regexs = [obj['name'].strip("'") for obj in kwargs['regexs']]
            fields = []
            fields_type = {}
            init_kwargs = {}
            name, field_str = name_re.match(name).groups()
            if field_str:
                for field, type, default in argument_re.findall(',' + field_str):
                    fields.append(field)
                    if type != '':
                        fields_type[field] = type[1:]
                    if default != '':
                        init_kwargs[field] = eval(default[1:])
            _spt = ['def {0}(condit, vm):'.format(name)]
            for field in fields:
                _spt += ['  {0} = {1}(condit["{0}"])'.format(field, fields_type[field])]
            if len(scripts) == 1:
                scripts[0] = 'return ' + scripts[0]
            for text in scripts:
                text = vm_getProp_re.sub(r'vm.getProp("\1")', text)
                text = vm_getPropRef_re.sub(r'vm.getProp(\1)', text)
                _spt += ['  ' + text]
            func_text = '\n'.join(_spt)
            
            if typename == 'Condit':
                ct = CreatorType(name, fields, init_kwargs=init_kwargs, inherit=ConditCreatorType)
                maker.CONDIT[name] = func_text
                for regex in regexs:
                    maker.condit_database[regex] = ct
            if typename == 'React':
                init_kwargs['reacts'] = []
                ct = CreatorType(name, fields, init_kwargs=init_kwargs, inherit=BlockCreatorType)
                maker.REACT[name] = func_text
                for regex in regexs:
                    maker.react_database[regex] = ct
            return (regexs, ct, name, func_text)
        return object_creator


class ImportCreatorType(CreatorType):
    def make_creator(self, typename):
        def object_creator(maker, *args, **kwargs):
            filename = args[0]
            if filename in maker.filenames:
                return
            data = yaml.compose(filename, ProcessLoader)
            root = Builder.common_build(maker, Root, None, data)
            root['filename'] = filename
            maker.imports(root, remote=True)
            return root
        return object_creator
        
class SimpleDictCreatorType(CreatorType):
    def make_creator(self, typename):
        def object_creator(maker, *args, **kwargs):
            assert len(args) == 0
            return dict(kwargs)
        return object_creator



class RootMaker:
    builder_list = []
    translate_attr_table = {
        # '描述': 'desc',
    }
    condit_database = OrderedDict()
    react_database = OrderedDict()
    def __init__(self):
        self.collections = OrderedDict()
        self.root = OrderedDict()
        self.CONDIT = {}
        self.REACT = {}
        self.filenames = []
        
    def add(self, object):
        if 'type' in object:
            collection = self.collections.setdefault(object['type'], OrderedDict())
        if 'name' in object:
            collection[object['name']] = object
        
    def imports(self, root, remote=False):
        for key in 'plots statuses'.split(' '):
            self.root.setdefault(key, []).extend(root[key])
        if not remote:
            self.root['storyname'] = root['storyname']
        else:
            self.filenames.append(root['filename'])
            
    def parse(self, filename):
        data = yaml.compose(filename, ProcessLoader)
        object = Builder.common_build(self, Root, None, data)
        self.imports(object)
        return self.root


ConditCreatorType = CreatorType('Condit', 'name condits and_combine', OrderedDict([('condits', []), ('and_combine', True)]))
# trigger = name
ListenCreatorType = CreatorType('Listen', 'name condits', OrderedDict([('condits', [])]))
BlockCreatorType = CreatorType('Block', 'name condits reacts', OrderedDict([('condits', [])]))
OptionCreatorType = CreatorType('Option', 'is_option default', OrderedDict([('is_option', True), ('default', False)]), inherit=BlockCreatorType)
EventCreatorType = CreatorType('Event', 'listens', inherit=BlockCreatorType)
StatusCreatorType = CreatorType('Status', 'effects events', OrderedDict([('effects', []), ('events', []), ('reacts', [])]), inherit=BlockCreatorType)
PlotCreatorType = CreatorType('Plot', '', inherit=StatusCreatorType)


RootMaker.builder_list = [
    Builder(ImportCreatorType('Import', 'name'), '$[引用] ', 'imports'),
    Builder(InstCreatorType('Condit', ['name', 'regexs', CreatorType.NO_CHECK], OrderedDict([('regexs', [])])), 'Condit function ', 'CONDIT'),
    Builder(InstCreatorType('React', ['name', 'regexs', CreatorType.NO_CHECK], OrderedDict([('regexs', [])])), 'React function ', 'REACT'),
    Builder(CreatorType('Regex', ['name']), '~ ', 'regexs'),

    Builder(StatusCreatorType, '$[狀態] ', 'statuses'),
    Builder(StatusCreatorType, '$[物品] ', 'statuses'),
    Builder(PlotCreatorType, '$[情結] ', 'plots'),
    Builder(OptionCreatorType, '$[選項] ', 'reacts'),
    Builder(OptionCreatorType, '$[預設] ', 'reacts', extra_attribs=OrderedDict([('default', True)])),
    Builder(BlockCreatorType, '$[後果] ', 'reacts', ksub_cls=RootMaker.condit_database, ksub_belong='condits'),
    # TODO: 把事件的功能做好
    Builder(ListenCreatorType, '$[每當] ', 'listens'),
    Builder(EventCreatorType, '$[事件] ', 'events'),
    Builder(CreatorType(subclasses=RootMaker.react_database), '< ', 'reacts'),
    Builder(SimpleDictCreatorType('Properties', [CreatorType.NO_CHECK]), '<-', 'properties'),
    Builder(CreatorType('Effect', 'name condits properties'),
            '$[影響] ', 'effects', ksub_cls=RootMaker.condit_database, ksub_belong='condits', extra_attribs=OrderedDict([('condits', []), ('properties', [])])),
    
    # noop
    Builder(CreatorType(subclasses={'': CreatorType('Block', '', OrderedDict([('reacts', [])]), inherit=BlockCreatorType)}), '<', 'reacts'),
    Builder(CreatorType(subclasses=RootMaker.condit_database), '$[條件] ', 'condits', extra_attribs=OrderedDict([('and_combine', True)])),
    Builder(CreatorType(subclasses=RootMaker.condit_database), '$[符合] ', 'condits', extra_attribs=OrderedDict([('and_combine', False)])),
]

Root = CreatorType('Root', 'storyname plots statuses imports CONDIT REACT',
        OrderedDict([('storyname', 'noname'), ('plots', []), ('statuses', []), ('imports', []), ('CONDIT', []), ('REACT', [])])
)

# root = RootMaker().parse('sample2.yaml')
# import pprint
# pp = pprint.PrettyPrinter(indent=1)
# pp.pprint(root)

