import random
from collections import OrderedDict
from input_test import Inputer, NumberCommand, OneCharCommand

def _asdict(o):
    return dict(zip(o._fields, o))
    
    
class Lookup:
    def __init__(self):
        self.table = {}
        
    def iterObject(self, key):
        array = self.table.get(key, [])
        for object, subject in array:
            yield object
            
    def add(self, key, object, subject):
        self.table.setdefault(key, []).append((object, subject))
        
    def removeSubject(self, subject):
        for key, array in self.table.items():
            removes = []
            for i, (_object, _subject) in enumerate(array):
                if subject == _subject:
                    removes.append(i)
            for i in reversed(removes):
                array.pop(i)

# class Status:

    # def fire(self, event_name):
        
class BlockRuntime:
    def __init__(self, block_photo):
        self.block_photo = block_photo
        self.program_count = 0
        self.programs = []
        self.queue_on_exit = []
        
        _options = None
        for subblock in block_photo['reacts']:
            if subblock['type'] == 'Option':
                _options = [subblock] if _options is None else _options + [subblock]
            else:
                if _options:
                    self.programs.append(_options)
                    _options = None
                self.programs.append(subblock)
        if _options:
            self.programs.append(_options)
            
    def queue(self, block_runtime):
        self.queue_on_exit.append(block_runtime)
        
    def avaliable_options(self, vm, options):
        _avaliable_options = []
        default_option = None
        for option in options:
            if 'default' in option and option['default'] and vm.vaildate(option):
                default_option = option
                continue
            if vm.vaildate(option):
                _avaliable_options.append(option)
        return _avaliable_options, default_option
        
    def next(self, vm):
        if self.program_count >= len(self.programs):
            if self.queue_on_exit:
                return ('PUSH', self.queue_on_exit.pop(0))
            return ('POP', None)
        if self.program_count == 0:
            if not vm.vaildate(self.block_photo):
                return ('INVAILD', None)
                
        subblock = self.programs[self.program_count]
        self.program_count += 1
        
        if isinstance(subblock, list):
            # do options
            selected = None
            avaliable_options, default_option = self.avaliable_options(vm, subblock)
            
            if avaliable_options:
                for i, option in enumerate(avaliable_options):
                    vm.inputer.print_('{}. {}'.format(i+1, option['name'].format(option)))    
                sel = vm.except_input(lambda v: isinstance(v, int), [NumberCommand(1, len(avaliable_options))])
                selected = avaliable_options[min(max(1, int(sel)), len(avaliable_options)) - 1]
            else:
                if default_option:
                    selected = default_option
            if selected:
                return ('PUSH', BlockRuntime(selected))
        else:
            # do react
            react_type = subblock['type']
            if react_type != 'Block':
                react_func = vm.react_database[react_type]
                react_func(subblock, vm)
            if 'reacts' in subblock and subblock['reacts']:
                return ('PUSH', BlockRuntime(subblock))
            #self.trigger(react_type)
        return ('OK', None)
            
        
                
        
class VM:
    def __init__(self):
        self.effect_lookup = Lookup()
        self.event_lookup = Lookup()
        self.properties = {}
        self.statuses = {}
        
        self.status_database = {}
        self.condit_database = {}
        self.react_database = {}
        self.talker = None
        self.inputer = Inputer()
        
        self.stack = []
        
    def setProp(self, key, value):
        self.properties[key] = value
        
    def alterProp(self, key, change):
        base = self.properties.get(key, 0)
        self.properties[key] = base + change
        
    def getProp(self, key, includes=(), excludes=()):
        base = self.properties.get(key, None)
        for effect in self.effect_lookup.iterObject(key):
            if key in effect['properties'] and self.vaildate(effect, includes, excludes):
                base = (base or 0) + effect['properties'][key]
        return base
    
    def conutStatus(self, status_name):
        i = 0
        for name, instance in self.statuses:
            if name == status_name:
                i += 1
        return i
        
    def hasStatus(self, status_name):
        return self.conutStatus(status_name) != 0

    def addStatus(self, status_name):
        assert status_name in self.status_database
        status = self.status_database[status_name]
        if status['limit'] and self.hasStatus(status_name):
            return
        instance = object()
        self.statuses.append((status_name, instance))
        for effect in status['effects']:
            for key in effect['properties']:
                self.effect_lookup.add(key, effect, instance)
        for event in status['events']:
            for listen in event['listens']:
                self.event_lookup.add(listen, event, instance)
        self.trigger('ADD_STAUTS')
        
    def removeStatus(self, status_name):
        if not self.hasStatus(status_name):
            return
        remove_idx = None
        for i, (name, instance) in enumerate(self.statuses):
            if name == status_name:
                remove_idx = id
                break
        self.trigger('REMOVE_STAUTS')
        if remove_idx is not None:
            self.statuses.pop(remove_idx)
            self.effect_lookup.removeSubject(instance)
            self.event_lookup.removeSubject(instance)
    
    def vaildate(self, block, tag_includes=None, tag_excludes=None):
        if 'tags' in block:
            if tag_includes:
                for tag in block['tags']:
                    if tag not in tag_includes:
                        return False
            if tag_excludes:
                for tag in block['tags']:
                    if tag in tag_excludes:
                        return False
                        
        if 'condits' in block and block['condits']:
            and_combine = None
            for condit in block['condits']:
                if and_combine is None:
                    and_combine = condit['and_combine']
                assert and_combine == condit['and_combine']
                
            for condit in block['condits']:
                condit_func = self.condit_database[condit['type']]
                # vaildate child node
                ok = self.vaildate(condit)
                # vaildate self
                ok = ok and condit_func(condit, self)
                if and_combine and not ok:
                    return False
                elif not and_combine and ok:
                    return True
            # default all pass value of AND=True or OR=False
            return and_combine
            
        return True

        
    def trigger(self, react_type):
        for event in self.event_lookup.iterObject(react_type):
            self.enter(event)
    
    
    
    '''
    
    def do_react(self, react):
        react_type = react['type']
        if react_type != 'Block':
            react_func = self.react_database[react_type]
            react_func(react, self)
        if 'reacts' in react:
            self.enter(react)
        self.trigger(react_type)
    
    
    def enter(self, block):
        if not self.vaildate(block):
            return
        
        _options = None
        _reacts = []
        for subblock in block['reacts']:
            if subblock['type'] == 'Option':
                _options = [subblock] if _options is None else _options + [subblock]
            else:
                if _options:
                    _reacts.append(_options)
                    _options = None
                _reacts.append(subblock)
        if _options:
            _reacts.append(_options)
            
        for react in _reacts:
            if isinstance(react, list):
                # do options
                selected = None
                avaliable_options, default_option = self.avaliable_options(react)
                
                if avaliable_options:
                    for i, option in enumerate(avaliable_options):
                        vm.inputer.print_('{}. {}'.format(i+1, option['name'].format(option)))    
                    sel = self.except_input(lambda v: isinstance(v, int), [NumberCommand(1, len(avaliable_options))])
                    selected = avaliable_options[min(max(1, int(sel)), len(avaliable_options)) - 1]
                else:
                    if default_option:
                        selected = default_option
                if selected:
                    self.enter(selected)
            else:
                # do react
                self.do_react(react)
    '''
    
    def enter(self, block):
        self.stack.append(BlockRuntime(block))
        while self.stack:
            action, target = self.stack[-1].next(self)
            if action == 'POP':
                self.stack.pop()
            if action == 'PUSH':
                self.stack.append(target)
            
    def except_input(self, func, commands):
        self.inputer.commands = [] + commands
        input = self.inputer.tick()
        while not func(input):
            input = self.inputer.tick()
        return input
        
    def print_(self, string):
        self.inputer.print_(string)
        self.except_input(lambda v: v == 'enter', [OneCharCommand('[enter]', 'enter')])
        
    def next(self):
        for status in self.statuses.values():
            self.enter(status)
        
        plot = self.talker.choice_plot()
        if plot:
            self.enter(plot)
            return True
        return False
        
    def forever(self):
        while self.next():
            pass
    
    def setup(self, talker):
        talker.vm = self
        self.talker = talker


class Talker:
    def __init__(self):
        self.plot_database = {}
        self.next_plot = None
        self.vm = vm
        
    def choice_plot(self):
        if self.next_plot:
            plot = self.plot_database[self.next_plot]
            self.next_plot = None
            return plot
        for plot in self.plot_database.values():
            if self.vm.vaildate(plot):
                return plot
    
import yaparser
maker = yaparser.RootMaker()
maker.parse('sample2.yaml')

vm = VM()
for name, script in maker.CONDIT.items():
    loc = {}
    exec(script, globals(), loc)
    func = loc[name]
    maker.CONDIT[name] = func
    
for name, script in maker.REACT.items():
    loc = {}
    exec(script, globals(), loc)
    func = loc[name]
    maker.REACT[name] = func
    
vm.condit_database = maker.CONDIT
vm.react_database = maker.REACT

talker = Talker()
talker.plot_database = OrderedDict((p['name'], p) for p in maker.root['plots'])

vm.setup(talker)
vm.next()

# while vm.next():
    # print('-'*50)
    # pass


