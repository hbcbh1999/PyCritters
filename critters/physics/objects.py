''' This module provides convenience classes to make physics primatives.

It is intended to be very bare-bones and does not supply these primatives
with mesh, texture, lighting, or even color information.
'''

from bullet.bullet import (
    Vector3, Transform,
    DefaultMotionState, RigidBody,
    BoxShape, StaticPlaneShape)

class PhysicsObject(object):
    __identifierCount = 0

    def __init__(self):
        self.__identifier = PhysicsObject.__identifierCount
        PhysicsObject.__identifierCount += 1

    identifier = property(lambda (self): self.__identifier)
        

class Boxi(PhysicsObject):
    
    def __init__(self, position, size, mass=None, density=1.0, restitution=0.9):
        PhysicsObject.__init__()
        self.size = size
        if mass == None:
            mass = density * self.size.x * self.size.y * self.size.z
        shape = BoxShape(size*0.5)
        transform = Transform()
        transform.setIdentity()
        transform.setOrigin(position)
        
        motion = DefaultMotionState()
        motion.setWorldTransform(transform)
        
        self.body = RigidBody(motion, shape, mass)
        self.body.setRestitution(restitution)
        
        self.motion = motion
        

class StaticPlane(PhysicsObject):

    def __init__(self, normalVec, distToOrigin):
        # Vector3, scalar
        PhysicsObject.__init__()
        shape = StaticPlaneShape(normalVec, distToOrigin)
        
        self.body = RigidBody(None, shape, 0.0)
