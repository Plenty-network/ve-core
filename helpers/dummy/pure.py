# A purely dummy contract for only checking tez flow

import smartpy as sp


class Pure(sp.Contract):
    def __init__(self):
        self.init()

    @sp.entry_point
    def hello_world(self):
        pass
