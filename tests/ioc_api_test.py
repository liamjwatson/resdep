"""
Can't mock devsup due to EPICS base dependencies (i think).
UNIT tests here are not suitable.
Moving to System integration tests either on a VM or container
"""         
# import pytest
# 
# import devsup.db
# import devsup.util
# import devsup.hooks
# 
# from resdep.ioc_api import IocApi, IocApiContract
# 
# @pytest.fixture
# def ioc_api():
#     return IocApi()
# 
# class MockStoppableThread():
#     """ 
#     Mock stoppable thread from devsup.util
#     """
#     def start(*args, **kwargs):
#         pass
# 
#     def join(*args, **kwargs):
#         pass
# 
# def mock_addHook(*args, **kwargs):
#     """
#     mock addHook() function from devsup.hooks
#     """
#     pass
# 
# def mock_devsup(monkeypatch):
#     """
#     Mock the stoppable thread and the hooks.adhook in that in the IocApi init.
#     """
#     monkeypatch.setattr(devsup.util, "StoppableThread", MockStoppableThread)
#     monkeypatch.setattr(devsup.hooks, "addHook", mock_addHook)
# 
# def test_contract(ioc_api, mock_devsup):
#     assert isinstance(ioc_api, IocApiContract)
#     
