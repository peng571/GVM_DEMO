from baseparser import *


def mark(text, p):
    return Mark(name='<code>', index=p, line=1, column=p, buffer=text, pointer=p)
    
def scalar_text(text):
    return yaml.ScalarNode('tag:yaml.org,2002:str', text, mark(text, 0), mark(text, len(text)))

def label(text):
    return yaml_to_node(scalar_text(text))
    
def test():
    b = Builder('T ', 'imports', CreatorType('T', ''), minor_spliters=['|'])
    head, tails = b.key_match(label('T a | c | d  |e'))
    assert head == 'a '
    assert tails[0] == '| c '
    assert tails[1] == '| d  '
    assert tails[2] == '|e'

    b = Builder('T ', 'imports', CreatorType('T', ''), minor_spliters=['||'])
    head, tails = b.key_match(label('T a || c || d  ||e'))
    assert head == 'a '
    assert tails[0] == '|| c '
    assert tails[1] == '|| d  '
    assert tails[2] == '||e'
    
    b = Builder('T ', 'imports', CreatorType('T', ''), minor_spliters=['<<', ','])
    head, tails = b.key_match(label('T a , c << d  ,e'))
    print(tails)
    assert head == 'a '
    assert tails[0] == ', c '
    assert tails[1] == '<< d  '
    assert tails[2] == ',e'
    
    
    Option1CreatorType = CreatorType('Option1', 'is_option', [('is_option', True)])
    builder = Builder('$[選項1] ', 'reacts', Option1CreatorType)
    parent_kwargs = {}
    builder.from_kvlist(None, label('$[選項1] '), ListNode(), parent_kwargs)
    print(parent_kwargs)
    
    
    Option1CreatorType = CreatorType('Option1', 'is_option', [('is_option', True)])
    builder1 = Builder('$[選項1] ', 'reacts1', Option1CreatorType)
    builder2 = Builder('$[選項2] ', 'reacts2', Option1CreatorType)
    m_builder = MultiBuilder([builder1, builder2])
    parent_kwargs = {}
    m_builder.from_kvlist(None, label('$[選項1] '), ListNode(), parent_kwargs)
    m_builder.from_kvlist(None, label('$[選項2] '), ListNode(), parent_kwargs)
    print(parent_kwargs)
    
    
    Option1CreatorType = CreatorType('Option1', 'is_option', [('is_option', True)])
    Option2CreatorType = CreatorType('Option2', 'is_option', [('is_option', True)])
    behavior = AsTypeBehavior(subclasses={r'123': Option2CreatorType})
    builder = Builder('$[選項1] ', 'reacts', Option1CreatorType, behaviors=[behavior])
    parent_kwargs = {}
    builder.from_kvlist(None, label('$[選項1] 123'), ListNode(), parent_kwargs)
    print(parent_kwargs)
    #builder.from_kvlist(None, label('$[選項] 456'), ListNode(), parent_kwargs)
    #print(parent_kwargs)
    
    
    Option1CreatorType = CreatorType('Option1', 'is_option', [('is_option', True)])
    Option3CreatorType = CreatorType('Option2', 'is_option reacts', [('is_option', True)])
    behavior = KSubBehavior(subclasses={r'123': Option1CreatorType}, ksub_belong='reacts')
    builder2 = Builder('$[選項3] ', 'reacts', Option3CreatorType, minor_spliters='$', behaviors=[behavior])
    
    parent_kwargs = {}
    builder2.from_kvlist(None, label('$[選項3] 123'), ListNode(), parent_kwargs)
    print(parent_kwargs)
    
    
    Option1CreatorType = CreatorType('Option1', 'is_option', [('is_option', True)])
    Option3CreatorType = CreatorType('Option2', 'is_option reacts', [('is_option', True)])
    builder1 = Builder('$[選項1] ', 'reacts', Option1CreatorType)
    behavior = BuildBehavior(builder=MultiBuilder([builder1]), star=True)
    builder2 = Builder('$[選項3] ', 'reacts', Option3CreatorType, minor_spliters='$', behaviors=[AsNameBehavior(), behavior])
    
    parent_kwargs = {}
    builder2.from_kvlist(None, label('$[選項3] $[選項1] $[選項1] '), ListNode(), parent_kwargs)
    print(parent_kwargs)
    
    
test()
