import os
import re
import copy
from collections import OrderedDict, namedtuple
from baseparser import *

class MakedCreatorType(CreatorType):
    def resolve(self, pack, parent=None):
        obj = super().resolve(pack, parent)
        obj['type'] = self.typename
        if obj['type'] == 'Assignment':
            v = str(obj['expr'])
            v = vm_getProp_re.sub(r'vm.getProp("\1")', v)
            v = vm_getPropRef_re.sub(r'vm.getProp(\1)', v)
            obj['expr'] = v
        if pack.maker:
            pack.maker.add(obj)
        return obj
    
class ActionCreatorType(MakedCreatorType):
    def resolve(self, pack, parent=None):
        obj = super().resolve(pack, parent)
        for k, v in self.init_kwargs.items():
            if obj[k] == 'None':
                obj[k] = v
        return obj
        
vm_getProp_re = re.compile(r'\$([A-Za-z0-9]+)')
vm_getPropRef_re = re.compile(r'\$\*([A-Za-z0-9]+)')
vm_getLocaleProp_re = re.compile(r'\\@([A-Za-z0-9]+)')
vm_getLocalePropRef_re = re.compile(r'\\@\*([A-Za-z0-9]+)')

class InstCreatorType(CreatorType):
    argument_re = re.compile(r'(?:,\s*([a-z_]+)(\:[a-z]+)?(\=[^ ,]+)?\s*)')
    name_re = re.compile(r'([A-Za-z0-9]+)\(([^\)]+)?\)')
    
    def pack(self, maker, root, args, kwargs):
        name = kwargs['name']
        scripts = args
        regexs = [obj.kwargs['name'].strip("'") for obj in kwargs['regexs']]
        
        fields = []
        fields_type = {}
        init_kwargs = {}
        name, field_str = self.name_re.match(name).groups()
        if field_str:
            for field, type, default in self.argument_re.findall(',' + field_str):
                fields.append(field)
                if type != '':
                    fields_type[field] = type[1:]
                if default != '':
                    init_kwargs[field] = eval(default[1:])
        _spt = ['def {0}(obj, vm, local):'.format(name)]
        for field in fields:
            _spt += ['  {0} = {1}(obj["{0}"])'.format(field, fields_type[field])]
        if len(scripts) == 1 and '\n' not in scripts[0]:
            scripts[0] = 'return ' + scripts[0]
        for text in sum([s.split('\n') for s in scripts], []):
            text = vm_getPropRef_re.sub(r'vm.getProp(\1)', text)
            text = vm_getProp_re.sub(r'vm.getProp("\1")', text)
            text = vm_getLocalePropRef_re.sub(r'vm.getLocaleProp(\1)', text)
            text = vm_getLocaleProp_re.sub(r'vm.getLocaleProp("\1")', text)
            _spt += ['  ' + text]
        func_text = '\n'.join(_spt)
        
        if self.typename == 'Condit':
            ct = ActionCreatorType(name, fields, init_kwargs=init_kwargs).inherit(maker.ConditCreatorType)
            maker.CONDIT[name] = func_text
            for regex in regexs:
                maker.condit_database[regex] = ct
        if self.typename == 'React':
            init_kwargs['reacts'] = []
            ct = ActionCreatorType(name, fields, init_kwargs=init_kwargs).inherit(maker.BlockCreatorType)
            maker.REACT[name] = func_text
            for regex in regexs:
                maker.react_database[regex] = ct
        if self.typename == 'Iter':
            ct = ActionCreatorType(name, fields, init_kwargs=init_kwargs)#.inherit(MakedCreatorType('_Iter', 'name'))
            maker.ITER[name] = func_text
            for regex in regexs:
                maker.iter_database[regex] = ct
        return None
        #return CreatorPack(self, maker, [], OrderedDict([('regexs', regexs), ('ct', ct), ('name', name), ('func_text', func_text)]))


class ImportCreatorType(CreatorType):
    def pack(self, maker, root, args, kwargs):
        basepath = os.path.dirname(root['filename'])
        filename = os.path.abspath(os.path.join(basepath, kwargs['name']))
        filename = os.path.relpath(filename, os.getcwd())
        if filename in maker.files:
            return maker.files[filename]
        root = maker.from_file(filename)
        root.kwargs['filename'] = filename
        maker.imports(root, remote=True)
        return CreatorPack(self, maker, root, args, kwargs)
        

        
class _ItemCreatorType(MakedCreatorType):
    def resolve(self, pack, parent=None):
        obj = super().resolve(pack, parent)
        skills = OrderedDict()
        for p in obj['purposes']:
            p['burnout'] = p['burnout'] == 'destory'
            p['level'] = int(p['level'])
            skills[p['skill']] = p
        obj['skills'] = skills
        return obj
        
class _BlockCreatorType(MakedCreatorType):
    def resolve(self, pack, parent=None):
        obj = super().resolve(pack, parent)
        
        # RandomChoice and RandomChoiceWithVariant
        if 'reacts' not in obj:
            return obj
            
        random_condits = OrderedDict()
        for react in obj['reacts']:
            for condit in react['condits']:
                if condit['type'] == 'RandomChoice':
                    condit['percent'] = int(condit['percent'])
                    random_condits.setdefault('', []).append(condit)
                    break
                elif condit['type'] == 'RandomChoiceWithVariant':
                    condit['percent'] = int(condit['percent'])
                    random_condits.setdefault(condit['variant'], []).append(condit)
                    break
        for group, condits in random_condits.items():
            base = 0
            for condit in condits:
                condit['base'] = base
                base += condit['percent']
            if base != 100:
                raise NodeError('base must == 100, but {}'.format(base), condits[0])
        if random_condits:
            setRandom_react = OrderedDict([('condits', []), ('reacts', []), ('type', 'setRandom')])
            obj['reacts'].insert(0, setRandom_react)
        return obj
        
class _PropertyCreatorType(_BlockCreatorType):
    def resolve(self, pack, parent=None):
        obj = super().resolve(pack, parent)
        removes = []
        locale_properties = OrderedDict()
        global_properties = OrderedDict()
        for k, v in obj.items():
            if k.startswith('\\@') or k.startswith('$'):
                v = str(v)
                v = vm_getPropRef_re.sub(r'vm.getProp(\1)', v)
                v = vm_getProp_re.sub(r'vm.getProp("\1")', v)
                v = vm_getLocalePropRef_re.sub(r'vm.getLocaleProp(\1)', v)
                v = vm_getLocaleProp_re.sub(r'vm.getLocaleProp("\1")', v)
                
                removes.append(k)
                if k.startswith('\\@'):
                    locale_properties[k[len('\\@'):]] = v
                if k.startswith('$'):
                    global_properties[k[len('$'):]] = v
        for k in removes:
            del obj[k]
        obj['locale_properties'] = locale_properties
        obj['global_properties'] = global_properties
        return obj

class RootMaker(Maker):
    def __init__(self):
        super().__init__()
        self.collections = OrderedDict()
        self.root = OrderedDict()
        self.condit_database = OrderedDict()
        self.react_database = OrderedDict()
        self.iter_database = OrderedDict()
        self.CONDIT = {}
        self.REACT = {}
        self.ITER = {}
        self.files = {}
        self.translate_table = {
            '標籤': 'tags'
        }
        self.create_builder_list()
        
        
    def add(self, obj):
        if 'type' in obj:
            collection = self.collections.setdefault(obj['type'], OrderedDict())
        if 'name' in obj:
            collection[obj['name']] = obj
        
    def imports(self, root, remote=False):
        root = root.creator_type.resolve(root)
        
        for key in 'plots statuses'.split(' '):
            self.root.setdefault(key, []).extend(root[key])
        if not remote:
            self.root['storyname'] = root['storyname']
        else:
            self.files[root['filename']] = root
            
    def parse(self, filename):
        obj = self.from_main_file(filename)
        self.imports(obj)
        return self.root

    def create_builder_list(self):
        self.Root = MakedCreatorType('Root', 'storyname plots statuses imports instructions',
                OrderedDict([('storyname', 'noname'), ('plots', []), ('statuses', []), ('imports', []), ('instructions', [])])
        )
        
        ConditCreatorType = MakedCreatorType('Condit', 'condits and_combine', [('condits', []), ('and_combine', True)])
        # trigger = name
        ListenCreatorType = MakedCreatorType('Listen', 'name condits', [('condits', [])])
        BlockCreatorType = _BlockCreatorType('Block', 'condits reacts tags', [('condits', []), ('tags', [])])
        OptionCreatorType = _BlockCreatorType('Option', 'name is_option default iters', [('is_option', True), ('default', False), ('iters', [])]).inherit(BlockCreatorType)
        EventCreatorType = _BlockCreatorType('Event', 'name listens', [('listens', [])]).inherit(BlockCreatorType)
        StatusCreatorType = _PropertyCreatorType('Status', 'name effects events', [('effects', []), ('events', []), ('reacts', [])]).inherit(BlockCreatorType)
        EffectCreatorType = _PropertyCreatorType('Effect', 'condits NO_CHECK')
        PlotCreatorType = _PropertyCreatorType('Plot', 'NO_CHECK').inherit(StatusCreatorType)
        
        
        
        self.ConditCreatorType = ConditCreatorType
        self.BlockCreatorType = BlockCreatorType
        
        CONDITCreatorType = InstCreatorType('Condit', 'name regexs NO_CHECK', [('regexs', [])])
        REACTCreatorType = InstCreatorType('React', 'name regexs NO_CHECK', [('regexs', [])])
        ITERCreatorType = InstCreatorType('Iter', 'name regexs NO_CHECK', [('regexs', [])])
        
        condit_ksub_behavior = KSubBehavior(subclasses=self.condit_database, ksub_belong='condits')
        condit_behavior = AsTypeBehavior(subclasses=self.condit_database)
        react_behavior = AsTypeBehavior(subclasses=self.react_database, strict=False)
        iter_behavior = AsTypeBehavior(subclasses=self.iter_database)
        noop_behavior = AsTypeBehavior(subclasses={r'^$': _BlockCreatorType('Block', '', [('reacts', [])]).inherit(BlockCreatorType)}, strict=False)
        
        short_builder = MultiBuilder([
            Builder('$[每當] ', 'listens', ListenCreatorType, behaviors=[AsNameBehavior()]),
            Builder('$[條件] ', 'condits', None, behaviors=[condit_behavior], extra_attribs=OrderedDict([('and_combine', True)])),
            Builder('$[符合] ', 'condits', None, behaviors=[condit_behavior], extra_attribs=OrderedDict([('and_combine', False)])),
            Builder('$[代入] ', 'iters', None, behaviors=[iter_behavior]),
            
            Builder('[每當] ', 'listens', ListenCreatorType, behaviors=[AsNameBehavior()]),
            Builder('[條件] ', 'condits', None, behaviors=[condit_behavior], extra_attribs=OrderedDict([('and_combine', True)])),
            Builder('[符合] ', 'condits', None, behaviors=[condit_behavior], extra_attribs=OrderedDict([('and_combine', False)])),
            Builder('[代入] ', 'iters', None, behaviors=[iter_behavior]),
        ])
        short_behavior = BuildBehavior(short_builder, star=True)
        
        instruction_builder = MultiBuilder([
            Builder('Condit function ', 'CONDIT', CONDITCreatorType, behaviors=[AsNameBehavior()]),
            Builder('React function ', 'REACT', REACTCreatorType, behaviors=[AsNameBehavior()]),
            Builder('Iter function ', 'ITER', ITERCreatorType, behaviors=[AsNameBehavior()]),
            Builder('~ ', 'regexs', CreatorType('Regex', 'name'), behaviors=[AsNameBehavior()]),
        ])
        
        self.builder.add_builder([
            Builder('$[引用] ', 'imports', ImportCreatorType('Import', 'name'), behaviors=[AsNameBehavior()]),
            Builder('$[指令集] ', 'instructions', CreatorType('Instruction', 'name CONDIT REACT ITER', [('CONDIT', []), ('REACT', []), ('ITER', [])]), locale_builder=instruction_builder, behaviors=[AsNameBehavior()]),
            
            Builder('$[狀態] ', 'statuses', StatusCreatorType, behaviors=[AsNameBehavior()]),
            
            Builder('$[情節] ', 'plots', PlotCreatorType, behaviors=[AsNameBehavior()]),
            Builder('$[選項] ', 'reacts', OptionCreatorType, behaviors=[AsNameBehavior(), short_behavior], minor_spliters=['[']),
            Builder('$[預設] ', 'reacts', OptionCreatorType, behaviors=[AsNameBehavior()], extra_attribs=OrderedDict([('default', True)])),
            Builder('$[後果] ', 'reacts', BlockCreatorType, behaviors=[condit_ksub_behavior]),
            
            
            Builder('$[事件] ', 'events', EventCreatorType, behaviors=[AsNameBehavior(), short_behavior], minor_spliters=['[']),
            Builder('$[影響] ', 'effects', EffectCreatorType, behaviors=[condit_ksub_behavior],
                    extra_attribs=OrderedDict([('condits', [])])),
            
            
        ])
        
        ItemCreatorType = _ItemCreatorType('Item', 'purposes is_item', [('purposes', []), ('is_item', True)]).inherit(StatusCreatorType)
        PurposeCreatorType = MakedCreatorType('Purpose', 'burnout skill level')
        purpose_bahavior = PropertyBahavior(subclasses={r'^(?P<skill>[^0-9]+)(?P<level>[1-9])$':True})
        self.builder.add_builder([
            Builder('消耗 ', 'purposes', PurposeCreatorType, behaviors=[purpose_bahavior], extra_attribs=[('burnout', 'destory')]),
            Builder('使用 ', 'purposes', PurposeCreatorType, behaviors=[purpose_bahavior], extra_attribs=[('burnout', 'noop')]),
            
            Builder('$[物品] ', 'statuses', ItemCreatorType, behaviors=[AsNameBehavior()]),
        ])
        
        self.builder.add_builder(short_builder.builders)
        self.builder.add_builder([
            # noop
            Builder('<', 'reacts', None, behaviors=[noop_behavior]),
            Builder('', 'reacts', None, behaviors=[react_behavior]),
        ])

# data = yaml.compose('sample2.yaml', ProcessLoader)
# print(yaml_to_node(data))

maker = RootMaker()
root = maker.parse('大宅1/main.txt')
import pprint
pp = pprint.PrettyPrinter(indent=1)
pp.pprint(root)
pp.pprint(maker.CONDIT)
pp.pprint(maker.REACT)
pp.pprint(maker.ITER)

