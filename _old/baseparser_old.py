import re
import copy
from collections import OrderedDict, namedtuple

from yaml_patch import ProcessLoader, Mark
import yaml

class NodeError(yaml.MarkedYAMLError):
    def __init__(self, problem, node, note=None):
        super().__init__(None, None, problem, node.start_mark, note=note)
        
class Node:
    def set_span(self, start_mark, end_mark):
        self._start_mark = start_mark
        self._end_mark = end_mark        
    @property
    def start_mark(self): return getattr(self, '_start_mark', None)
    @property
    def end_mark(self): return getattr(self, '_end_mark', None)

class Null:
    def __init__(self, value):
        self.value = value
    def __repr__(self):
        return 'null'
        
class Bool:
    def __init__(self, value):
        self.value = bool(value)
    def __bool__(self):
        return self.value
    def __repr__(self):
        return 'true' if self else 'false'
        
class NullNode(Null, Node): pass
class BoolNode(Bool, Node): pass
class IntNode(int, Node): pass
class StrNode(str, Node): pass    
class FloatNode(float, Node): pass
class ListNode(list, Node): pass
class DictNode(OrderedDict, Node): pass

from yaml.representer import Representer
from yaml.constructor import Constructor
yaml_representer = Representer()
yaml_constructor = Constructor()

def yaml_to_node(yaml_obj):
    if isinstance(yaml_obj, yaml.MappingNode):
        v = [(yaml_to_node(k), yaml_to_node(v)) for k, v in yaml_obj.value] 
        node = DictNode(v)
    elif isinstance(yaml_obj, yaml.SequenceNode):
        v = [yaml_to_node(v) for v in yaml_obj.value] 
        node = ListNode(v)
    elif isinstance(yaml_obj, yaml.ScalarNode):
        # 'tag:yaml.org,2002:bool'
        type = yaml_obj.tag.split(':')[2]
        type = type[0].upper() + type[1:] + 'Node'
        v = yaml_obj.value
        node = globals()[type](v)
    node.set_span(yaml_obj.start_mark, yaml_obj.end_mark)
    return node
    
def offset_mark(mark, offset):
    mark = copy.copy(mark)
    mark.column += offset
    mark.pointer += offset
    return mark


class Builder:
    def __init__(self, k_pattern, k_belong, creator_type, **kwargs):        
        self.k_pattern = k_pattern
        self.k_belong = k_belong
        self.creator_type = creator_type
        self.behaviors = kwargs.get('behaviors', None)
        self.minor_spliters = kwargs.get('minor_spliters', None)
        self.extra_attribs = kwargs.get('extra_attribs', OrderedDict())
        self.locale_builder = kwargs.get('locale_builder', None)
        if self.locale_builder:
            assert self.locale_builder.parent is None
            self.locale_builder.set_parent(self)
                    
        self.parent = None
        
    def set_parent(self, parent):
        self.parent = parent
        
    def get_locale_builder(self):
        p = self
        while(p):
            if p.locale_builder:
                return p    
            p = p.parent
        
    @classmethod
    def slice_text(cls, text, begin, end):
        sliced = StrNode(text[begin:end])
        sm = offset_mark(text.start_mark, begin)
        em = offset_mark(text.start_mark, end)
        sliced.set_span(sm, em)
        return sliced
        
    def key_match(self, key):
        assert isinstance(key, StrNode)
        if not key.startswith(self.k_pattern):
            return None, []
            
        def findpos(string):
            poses = [(i, string.find(sub)) for i, sub in enumerate(self.minor_spliters)]
            poses = [pos for pos in poses if pos[1] != -1]
            if not poses:
                return -1, None
            idx, pos = min(poses, key=lambda x: x[1])
            return pos, self.minor_spliters[idx]
            
        headpart_begin = len(self.k_pattern)
        entire_end = len(key)
        breaks = []
        if self.minor_spliters:
            target = key[headpart_begin:]
            pos, spliter = findpos(target)
            while(pos != -1):
                breaks.append(pos + (breaks[-1] if breaks else 0))
                target = key[breaks[-1]+len(spliter)+headpart_begin:]
                pos, next_spliter = findpos(target)
                if pos != -1:
                    pos += len(spliter)
                    spliter = next_spliter
                    
        breaks = [p + headpart_begin for p in breaks]
        if breaks:
            headpart = self.slice_text(key, headpart_begin, breaks[0])
            tailparts = [self.slice_text(key, begin, end) for begin, end in zip(breaks, breaks[1:] + [entire_end]) ]
        else:
            headpart = self.slice_text(key, headpart_begin, entire_end)
            tailparts = []
        return headpart, tailparts

    def _from_kvlist(self, maker, key, values, parent_kwargs):
        headpart, tailparts = self.key_match(key)
        
        if headpart is None:
            return None
            
        init_kwargs = DictNode(copy.deepcopy(self.extra_attribs))
        init_kwargs.set_span(key.start_mark, key.end_mark)
        
        _parts = [headpart] + tailparts
        parts = _parts[:]
        behaviors = list(self.behaviors or [])
        context = {'name': key, 'creator_type':self.creator_type}
        def do_beh(beh):
            if not parts:
                raise NodeError('need more part', _parts[-1])
            return beh.do(maker, self, parts.pop(0), init_kwargs, context)
        
        beh = behaviors.pop(0) if behaviors else None
        while beh and not beh.star:
            if not do_beh(beh):
                return False
                
            beh = behaviors.pop(0) if behaviors else None
        while beh and parts:
            do_beh(beh)
            
        obj = self.common_build(maker, context['creator_type'], context['name'], values, init_kwargs)
        parent_kwargs.setdefault(self.k_belong, []).append(obj)
        return True
        
    def from_kvlist(self, maker, key, values, parent_kwargs):
        try:
            return self._from_kvlist(maker, key, values, parent_kwargs)
        except Exception as e:
            raise NodeError(str(e), key)
            
    def common_build(self, maker, creator_type, name, kwlist, init_kwargs=None):
        #print(kwlist)
        assert isinstance(kwlist, ListNode)
        args = []
        build_kwargs = copy.deepcopy(creator_type.init_kwargs)
        build_kwargs.update(init_kwargs or {})
        kwlist_kwargs = DictNode()
        
        def from_kvlist(k, v):
            if self.get_locale_builder():
                return self.get_locale_builder().locale_builder.from_kvlist(maker, k, v, build_kwargs)
            return False

        for v in kwlist:
            if isinstance(v, DictNode):
                objk, objv = list(v.items())[0]
                trans_objk = maker.translate_table.get(objk, None)
                if trans_objk:
                    trans_objk = StrNode(trans_objk)
                    trans_objk.set_span(objk.start_mark, objk.end_mark)
                    objk = trans_objk
                # objk, objv is constructor
                if isinstance(objv, ListNode) and from_kvlist(objk, objv):
                    continue
                        
                # objk, objv is attributes
                kwlist_kwargs[objk] = objv
            else:
                if not isinstance(v, (ListNode, DictNode)):
                    if from_kvlist(v, ListNode()):
                        # element v is constructor
                        continue
                # element v is fixed-position attributes, maybe is array
                args.append(v)
        
        build_kwargs.update(kwlist_kwargs)
        
        # check args and kwargs of creation
        extra = list(creator_type.fields)
        #print(extra, list(build_kwargs.keys()))
        #print(args)
        for attr in build_kwargs.keys():
            if attr not in extra:
                if not(extra and creator_type.NO_CHECK in extra):
                    if attr in kwlist_kwargs:
                        raise NodeError('多餘的條目: {0}'.format(attr), attr)
                    else:
                        raise NodeError('多餘的預設條目: {0}'.format(attr), kwlist)
            else:
                extra.remove(attr)
                
        if 'name' in extra:
            args = [name] + args
        for arg in args:
            if len(extra) == 0:
                raise NodeError('多餘的條目', arg)
            if extra[0] != creator_type.NO_CHECK:
                extra.pop(0)
        
        if len(extra) > 0:
            if extra[0] != creator_type.NO_CHECK:
                raise NodeError('還有未指定的屬性: {}'.format(extra[0]), name)
        
        pack = creator_type.pack(maker, args, build_kwargs)
        return pack
        #obj = creator_type.creator(maker, *args, **build_kwargs)
        #return obj


class MultiBuilder(Builder):
    def __init__(self, builders):
        self.builders = []
        self.locale_builder = self
        for builder in builders:
            self.add_builder(builder)
                    
        self.parent = None
        
    def add_builder(self, builders):
        if not isinstance(builders, list):
            builders = [builders]
        for builder in builders:
            if builder.parent is not None:
                builder = copy.copy(builder)
            builder.set_parent(self)
            self.builders.append(builder)
        
    def from_kvlist(self, maker, key, values, parent_kwargs):
        for builder in self.builders:
            obj = builder.from_kvlist(maker, key, values, parent_kwargs)
            if obj:
                return True
        return False
        

class Behavior:
    def __init__(self, strict=True, star=False):
        self.strict = strict
        self.star = star
        
    @classmethod
    def text_match(cls, text, subclasses):
        assert isinstance(text, StrNode)
        for _regex, match_cls in subclasses.items():
            
            regex = re.compile(_regex)
            m = regex.match(text)
            if m:
                kwargs_list = DictNode()
                kwargs_list.set_span(text.start_mark, text.end_mark)
                for k, v in m.groupdict().items():
                    start, end = m.span(regex.groupindex[k])
                    sm, em = offset_mark(text.start_mark, start), offset_mark(text.start_mark, end)
                    k, v = StrNode(k), StrNode(v)
                    k.set_span(sm, em)
                    v.set_span(sm, em)
                    kwargs_list[k] = v
                return match_cls, kwargs_list
        return None, None
    
class AsNameBehavior(Behavior):
    def do(self, maker, builder, text, init_kwargs, context):
        context['name'] = text
        return True
        
class AsTypeBehavior(Behavior):
    def __init__(self, subclasses, **kwargs):
        super().__init__(**kwargs)
        self.subclasses = subclasses
        
    def do(self, maker, builder, text, init_kwargs, context):
        creator_type, kwlist = self.__class__.text_match(text, self.subclasses)
        if creator_type:
            init_kwargs.update(kwlist)
            context['creator_type'] = creator_type
            context['name'] = text
            return True
        elif self.strict:
            raise NodeError('找不到可符合的類別', text)
        return False
        
class KSubBehavior(Behavior):
    def __init__(self, subclasses, ksub_belong, **kwargs):
        super().__init__(**kwargs)
        self.subclasses = subclasses
        self.ksub_belong = ksub_belong
        
    def do(self, maker, builder, text, init_kwargs, context):
        creator_type, kwlist = self.__class__.text_match(text, self.subclasses)
        if creator_type:
            sub = builder.common_build(maker, creator_type, text, ListNode(), kwlist)
            init_kwargs.setdefault(self.ksub_belong, []).append(sub)
            return True
        elif self.strict:
            raise NodeError('找不到可符合的類別', text)
        return False
        
class BuildBehavior(Behavior):
    def __init__(self, builder, **kwargs):
        super().__init__(**kwargs)
        self.builder = builder
        
    def do(self, maker, builder, text, init_kwargs, context):
        if self.builder.from_kvlist(maker, text, ListNode(), init_kwargs):
            return True
        elif self.strict:
            raise NodeError('找不到可符合的類別', text)
        return False
        
CreatorPack = namedtuple('CreatorPack', 'creator_type maker args kwargs')

def unique_merge(iter1, iter2):
    merged = list(iter1)
    for item in iter2:
        if item not in merged:
            merged.append(item)
    return merged
    
class CreatorType:
    NO_CHECK = object()
    def __init__(self, typename=None, fields=None, init_kwargs=None):
        self.typename = typename
        self.fields = fields or []
        self.fields = list(self.fields) if not isinstance(self.fields, str) else fields.split(' ')
        for i in range(len(self.fields)):
            if self.fields[i] == 'NO_CHECK':
                self.fields[i] = self.NO_CHECK
                
        self.init_kwargs = init_kwargs or []
        if isinstance(self.init_kwargs, list):
            self.init_kwargs = OrderedDict(self.init_kwargs)
        self.fields = unique_merge(self.fields, self.init_kwargs.keys())
    
    def inherit(self, base):
        fields = unique_merge(base.fields, self.fields)
        init_kwargs = copy.deepcopy(base.init_kwargs)
        init_kwargs.update(self.init_kwargs)
        return self.__class__(self.typename, fields, init_kwargs)
        
    def pack(self, maker, args, kwargs):
        return CreatorPack(self, maker, args, kwargs)
    
    def resolve_children(self, target, parent=None):
        if isinstance(target, list):
            return [self.resolve_children(v, parent) for v in target]
        if isinstance(target, dict):
            return OrderedDict((k, self.resolve_children(v, parent)) for k, v in target.items())
        if isinstance(target, CreatorPack):
            return target.creator_type.resolve(target, parent)
        return target
        
    def resolve(self, pack, parent=None):
        obj = OrderedDict(pack.kwargs)
        for key, arg in zip(self.fields, pack.args):
            obj[key] = arg
        for k, v in obj.items():
            obj[k] = self.resolve_children(v, self)
        return obj

class SimpleDictCreatorType(CreatorType):
    def resolve(self, pack, parent=None):
        assert len(pack.args) == 0
        return dict(pack.kwargs)
        
class SimpleListCreatorType(CreatorType):
    def resolve(self, pack, parent=None):
        assert len(pack.kwrags) == 0
        return list(pack.args)
        
class Maker:
    def __init__(self):
        self.builder = MultiBuilder([])
        self.translate_table = {}
        
    def from_file(self, filename):
        data = yaml.compose(filename, ProcessLoader)
        data = yaml_to_node(data)
        pack = self.builder.common_build(self, self.Root, StrNode(filename), data)
        return pack
