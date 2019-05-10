#!/usr/bin/env sh

middleman build --verbose
middleman deploy --build-before
