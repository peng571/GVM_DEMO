import random
from collections import OrderedDict
from wcwidth import wcswidth
from inputview import Inputer, NumberCommand, OneCharCommand
    
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
    
def test_Lookup():
    lku = Lookup()
    a = object()
    b = object()
    c = object()
    d = object()
    lku.add('a', c, a)
    lku.add('b', c, b)
    lku.add('b', d, b)
    
    assert set([c]) == set(lku.iterObject('a'))
    assert set([c, d]) == set(lku.iterObject('b'))
    lku.removeSubject(b)
    assert set([]) == set(lku.iterObject('b'))
    
test_Lookup()




class StatusRuntime:
    def __init__(self):
        self.properties = {}
        
        
    def fire(self, event_name):
        pass
        
class BlockRuntime:
    def __init__(self, status, block_photo, local_vars={}):
        self.status = status
        self.block_photo = block_photo
        self.program_count = 0
        self.programs = []
        self.queue_on_exit = []
        # TODO: 階層可視性的問題
        self.local_vars = local_vars
        
        # 將options分組
        # TODO: 這個部份應該要移到parser
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
                default_option = BlockRuntime(self.status, option)
                default_option.title = option['name']
                continue
            if vm.vaildate(option):
                if option['iters']:
                    iter = option['iters'][0]
                    iter_func = vm.iter_database[iter['type']]
                    for obj in iter_func(iter, vm, self.local_vars):
                        block = BlockRuntime(self.status, option, {'it': obj})
                        block.title = '{}({}{})'.format(option['name'], obj['用法'], obj['名稱'])
                        _avaliable_options.append(block)
                else:
                    block = BlockRuntime(self.status, option)
                    block.title = option['name']
                    _avaliable_options.append(block)
                
        return _avaliable_options, default_option
        
    def next(self, vm):
        vm.current_status = self.status
        if self.program_count >= len(self.programs):
            if self.queue_on_exit:
                return ('PUSH', self.queue_on_exit.pop(0))
            return ('POP', None)
        if self.program_count == 0:
            if not vm.vaildate(self.block_photo):
                return ('POP', None)
                
        subblock = self.programs[self.program_count]
        self.program_count += 1
        
        if isinstance(subblock, list):
            # do options
            selected = None
            avaliable_options, default_option = self.avaliable_options(vm, subblock)
            
            if avaliable_options:
                for i, option in enumerate(avaliable_options):
                    # TODO: format local_vars
                    vm.inputer.print_('{}. {}'.format(i+1, option.title.format(option.block_photo)))    
                sel = vm.except_input(lambda v: isinstance(v, int), [NumberCommand(1, len(avaliable_options))])
                selected = avaliable_options[min(max(1, int(sel)), len(avaliable_options)) - 1]
            else:
                if default_option:
                    selected = default_option
            if selected:
                return ('PUSH', selected)
        else:
            # do react
            react_type = subblock['type']
            if react_type != 'Block':
                react_func = vm.react_database[react_type]
                react_func(subblock, vm, self.local_vars)
            if 'reacts' in subblock and subblock['reacts']:
                return ('PUSH', BlockRuntime(self.status, subblock))
            #self.trigger(react_type)
        return ('OK', None)
            
        
        
class StatusMixin:
    def __init__(self):
        super().__init__()
        self.status_database = {}
        self.effect_lookup = Lookup()
        self.event_lookup = Lookup()
        self.statuses = []
        
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
        # TODO: 正確的limit效果
        if 'limit' in status and status['limit'] and self.hasStatus(status_name):
            return
        instance = object()
        self.statuses.append((status_name, instance))
        if 'effects' in status:
            for effect in status['effects']:
                for key in effect['global_properties']:
                    self.effect_lookup.add(key, effect, instance)
        if 'events' in status:
            for event in status['events']:
                self.event_lookup.add(event['name'], event, instance)
                for listen in event['listens']:
                    self.event_lookup.add(listen, event, instance)
        #self.trigger('ADD_STAUTS')
        
    def removeStatus(self, status_name, count=1):
        remove_idx = None
        for i, (name, instance) in enumerate(self.statuses):
            if name == status_name:
                count -= 1
                if count == 0:
                    remove_idx = i
                    break
        if remove_idx is not None:
            #self.trigger('REMOVE_STAUTS')
            self.statuses.pop(remove_idx)
            self.effect_lookup.removeSubject(instance)
            self.event_lookup.removeSubject(instance)
    
        
class PropertySetMixin:
    # need vm.effect_lookup
    def __init__(self):
        super().__init__()
        self.properties = {}
        
    def setProp(self, key, value, properties=None):
        properties = self.properties if properties is None else properties
        properties[key] = value
        
    def alterProp(self, key, change, properties=None):
        properties = self.properties if properties is None else properties
        base = properties.get(key, 0)
        properties[key] = base + change
        
    def getProp(self, key, includes=(), excludes=(), properties=None, position='global_properties'):
        properties = self.properties if properties is None else properties
        base = self.properties.get(key, None)
        for effect in self.effect_lookup.iterObject(key):
            if key in effect[position] and self.vaildate(effect, includes, excludes):
                base = (base or 0) + effect[position][key]
        return base
    
    def setLocaleProp(self, key, value):
        return self.setProp(key, value, self.current_status.properties)
        
    def alterLocaleProp(self, key, change):
        return self.alterProp(key, change, self.current_status.properties)
    
    def getLocaleProp(self, key, includes=(), excludes=()):
        return self.getProp(key, includes, excludes, self.current_status.properties, 'locale_propreties')
    
    
class BlockMixin:
    # need vm.event_lookup
    def __init__(self):
        super().__init__()
        self.condit_database = {}
        self.react_database = {}
        self.iter_database = {}
        self.stack = []
        
    def vaildate(self, block, local={}, tag_includes=None, tag_excludes=None):
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
                ok = ok and condit_func(condit, self, local)
                if and_combine and not ok:
                    return False
                elif not and_combine and ok:
                    return True
            # default all pass value of AND=True or OR=False
            return and_combine
            
        return True
        
    def trigger(self, event_name, route='queue'):
        for event, status in self.event_lookup.table.get(event_name, []):
            if route == 'queue':
                self.stack[-1].queue_on_exit.append(BlockRuntime(status, event))
            if route == 'fire':
                self.stack.append(BlockRuntime(status, event))
            
    def callEvent(self, event_name):
        self.trigger(event_name, 'fire')
        
    def enter(self, block):
        self.addStatus(block['name'])
        self.stack.append(BlockRuntime(None, block))
        while self.stack:
            action, target = self.stack[-1].next(self)
            if action == 'POP':
                self.stack.pop()
            if action == 'PUSH':
                self.stack.append(target)
        self.removeStatus(block['name'])


class TalkerMixin:
    def __init__(self):
        super().__init__()
        self.plot_database = {}
        self.setProp('nextPlot', '')
        self.setProp('variant', '')
        
    def choice_plot(self):
        next_plot = self.getProp('nextPlot')
        if next_plot:
            plot = self.plot_database[next_plot]
            return plot
        for plot in self.plot_database.values():
            if self.vaildate(plot):
                return plot

class InputMixin:
    def __init__(self):
        super().__init__()
        self.inputer = Inputer()
    
    def except_input(self, func, commands):
        self.inputer.commands = [] + commands
        input = self.inputer.tick()
        while not func(input):
            input = self.inputer.tick()
        return input
        
    def print_(self, string):
        self.inputer.print_(string)
        self.except_input(lambda v: v == 'enter', [OneCharCommand('[enter]', 'enter')])
        
    
class ItemMixin:
    def __init__(self):
        super().__init__()
        self.max_items = 12
        # for c in range(ord('A'), ord('O')):
            # self.status_database[chr(c)] = {'is_item': True, 'reacts':[]}
            # self.addItem(chr(c))
            
    def iter_item(self):
        for status_name, _ in self.statuses:
            status = self.status_database[status_name]
            if 'is_item' in status and status['is_item']:
                yield status_name
    
    def iterItem(self):
        for name in self.iter_item():
            yield self.status_database[name]
        
    def countItem(self, item_name):
        return self.countItem(item_name)
        
    def hasItem(self, item_name):
        return self.hasStatus(item_name)
    
    def addItem(self, item_name):
        self.inputer.print_('你獲得了 {}'.format(item_name))
        self.addStatus(item_name)
        if len(list(self.iter_item())) > self.max_items:
            self.prompt_drop()
            
    def removeItem(self, item_name, count=1):
        self.removeStatus(item_name, count)
    
    def prompt_drop(self):
        items = list(self.iter_item())
        self.inputer.print_('背包裝不下了, 選擇你要丟棄的物品...')
        for i in range(len(items)):
            if len(items) < 10:
                self.inputer.print_('{}.{}'.format(i+1, items[i]))
            else:
                self.inputer.print_('{:02d}.{}'.format(i+1, items[i]))
                
        sel = self.except_input(lambda v: isinstance(v, int), [NumberCommand(1, len(items))])
        
        removed = items[int(sel) - 1]
        count = items[:int(sel) - 1].count(removed) + 1
        self.removeItem(removed, count)
        self.inputer.print_('你丟掉了 {}'.format(removed))
        
    def print_player(self):
        super().print_player()
        items = list(self.iter_item())
        assert len(items) <= self.max_items
        while len(items) < self.max_items:
            items.append('_')
        for i in range(0, 12, 4):
            itemstring = [ item + ' ' * (15 - wcswidth(item)) for item in items[i:i+4]]
            self.inputer.print_('| {} | {} | {} | {} |'.format(*itemstring))
        self.inputer.print_('='*26)
        
class PlayerMixin:
    def __init__(self):
        super().__init__()
        self.setProp('hp', 30)
        self.setProp('hp_max', 30)
        self.setProp('mp', 30)
        self.setProp('mp_max', 30)
        
    def print_player(self):
        self.inputer.print_('====== {0}/{1}  {2}/{3} ======'.format(
            self.getProp('hp'),
            self.getProp('hp_max'),
            self.getProp('mp'),
            self.getProp('mp_max'),
        ))
        
        
class VM(ItemMixin, PlayerMixin, TalkerMixin, BlockMixin, PropertySetMixin, StatusMixin, InputMixin):
    def __init__(self):
        super().__init__()
        
        
    def next(self):
        self.print_player()
        for status_name, _ in self.statuses:
            status = self.status_database[status_name]
            self.enter(status)
        
        plot = self.choice_plot()
        if plot:
            self.enter(plot)
            return True
        return False
        
    def forever(self):
        while self.next():
            pass
    

    
if __name__ == '__main__':
    import yaparser
    maker = yaparser.RootMaker()
    maker.parse('新/main.txt')

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
        
    for name, script in maker.ITER.items():
        loc = {}
        exec(script, globals(), loc)
        func = loc[name]
        maker.ITER[name] = func
        
    vm.condit_database = maker.CONDIT
    vm.react_database = maker.REACT
    vm.iter_database = maker.ITER
    
    vm.plot_database = OrderedDict((p['name'], p) for p in maker.root['plots'])
    vm.status_database = OrderedDict((p['name'], p) for p in maker.root['statuses'])
    vm.status_database.update( OrderedDict((p['name'], p) for p in maker.root['plots']) )
    
    vm.setProp('nextPlot', '小型遭遇戰')
    vm.addStatus('公用')
    vm.forever()

    # while vm.next():
        # print('-'*50)
        # pass


