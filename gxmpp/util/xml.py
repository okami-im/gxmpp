def element_eq(e1, e2):
    # adapted from https://stackoverflow.com/a/24349916
    # CC BY-SA 3.0
    if e1.tag != e2.tag:
        return False
    if e1.text != e2.text:
        return False
    if e1.tail != e2.tail:
        return False
    if e1.attrib != e2.attrib:
        return False
    if len(e1) != len(e2):
        return False
    return all(map(lambda p: element_eq(p[0], p[1]), zip(e1, e2)))
