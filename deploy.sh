#!/usr/bin/env sh

export LANG=C.UTF-8

middleman build --verbose
middleman deploy --build-before
