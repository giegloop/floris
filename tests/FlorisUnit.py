"""
Copyright 2017 NREL

Licensed under the Apache License, Version 2.0 (the "License"); you may not use
this file except in compliance with the License. You may obtain a copy of the
License at http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed
under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from .BaseObject_test import BaseObjectTest
from .Coordinate_test import CoordinateTest
from .FlowField_test import FlowFieldTest

class FlorisUnitTest():
    def __init__(self):
        self.baseobject = BaseObjectTest()
        self.coordinate = CoordinateTest()
        self.flowfield = FlowFieldTest()

    def run_tests(self):
        self.baseobject.test_all()
        self.coordinate.test_all()
        self.flowfield.test_all()