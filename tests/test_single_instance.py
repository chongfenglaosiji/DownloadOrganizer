# -*- coding: utf-8 -*-
"""单实例锁测试（同进程内验证互斥语义；跨进程由集成测试覆盖）。"""
from download_organizer.single_instance import SingleInstance


def test_second_acquire_fails_while_held():
    si = SingleInstance()
    si2 = SingleInstance()
    try:
        assert si.acquire() is True
        assert si2.acquire() is False   # 持锁期间再次获取失败
    finally:
        si.release()


def test_release_allows_reacquire():
    si = SingleInstance()
    si.acquire()
    si.release()
    si2 = SingleInstance()
    try:
        assert si2.acquire() is True    # 释放后可重新获取
    finally:
        si2.release()


def test_double_release_safe():
    si = SingleInstance()
    si.acquire()
    si.release()
    si.release()   # 重复释放不抛错


def test_context_manager():
    with SingleInstance() as si:
        assert si._acquired is True
    # 退出上下文后已释放
    si2 = SingleInstance()
    try:
        assert si2.acquire() is True
    finally:
        si2.release()
