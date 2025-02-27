#!/pxrpythonsubst
#
# Copyright 2017 Pixar
#
# Licensed under the terms set forth in the LICENSE.txt file available at
# https://openusd.org/license.

# pylint: disable=dict-keys-not-iterating

from __future__ import print_function

from pxr import Usd, Vt, Sdf, Tf
import unittest

stage = Usd.Stage.Open("./Test.usda")
testPrim = stage.GetPrimAtPath("/CollectionTest")
testExprPrim = stage.GetPrimAtPath("/CollectionExprTest")

geom = stage.GetPrimAtPath("/CollectionTest/Geom")
box = stage.GetPrimAtPath("/CollectionTest/Geom/Box")
materials = stage.GetPrimAtPath("/CollectionTest/Materials")

shapes = stage.GetPrimAtPath("/CollectionTest/Geom/Shapes")
sphere = stage.GetPrimAtPath("/CollectionTest/Geom/Shapes/Sphere")
hemiSphere1 = stage.GetPrimAtPath("/CollectionTest/Geom/Shapes/Sphere/Hemisphere1")
hemiSphere2 = stage.GetPrimAtPath("/CollectionTest/Geom/Shapes/Sphere/Hemisphere2")
cube = stage.GetPrimAtPath("/CollectionTest/Geom/Shapes/Cube")
cylinder = stage.GetPrimAtPath("/CollectionTest/Geom/Shapes/Cylinder")
cone = stage.GetPrimAtPath("/CollectionTest/Geom/Shapes/Cone")

def _DebugCollection(collection):
    print("Debugging Collection: ", collection.GetName())
    mquery = collection.ComputeMembershipQuery()
    print("-- Included Objects -- ")
    incObjects = Usd.CollectionAPI.ComputeIncludedObjects(mquery, stage)
    for obj in incObjects: print(".. ", obj.GetPath()) 

class TestUsdCollectionAPI(unittest.TestCase):
    def tearDown(self):
        # Discard any edits made to layers
        stage.Reload()
        pass

    def checkQuery(self, mquery, stage, verbose=False):
        # Cross-check the mquery between ComputeIncludedPathsFromCollection(),
        # IsPathIncluded(), and the expression produced by
        # ComputePathExpressionFromCollectionMembershipQueryRuleMap().

        # Compute includes from the membership query.
        includes = set(Usd.ComputeIncludedPathsFromCollection(
            query=mquery, stage=stage))
        
        # Fetch all paths from the stage, then cross-check.
        allPaths = set()
        for prim in stage.Traverse():
            allPaths.add(prim.GetPath())
            allPaths.update([prop.GetPath() for prop in prim.GetProperties()])

        # Check all paths with query.IsPathIncluded() API.
        for path in allPaths:
            if path in includes:
                self.assertTrue(mquery.IsPathIncluded(path),
                                msg='query should include {}'.format(path))
            else:
                self.assertFalse(mquery.IsPathIncluded(path),
                                 msg='query should exclude {}'.format(path))

        # Get path expression.
        pathExpr = \
            Usd.ComputePathExpressionFromCollectionMembershipQueryRuleMap(
                mquery.GetAsPathExpansionRuleMap())

        # Check all paths against expression Match() API.
        matchEval = Sdf._MakeBasicMatchEval(pathExpr.GetText())
        for path in allPaths:
            if path in includes:
                self.assertTrue(matchEval.Match(path),
                                msg='expr should match {}'.format(path))
            else:
                self.assertFalse(matchEval.Match(path),
                                 msg='expr should not match {}'.format(path))

    def test_AuthorCollections(self):
        # ----------------------------------------------------------
        # Test an explicitOnly collection.
        self.assertTrue(Usd.CollectionAPI.CanApply(testPrim, 
                "test:Explicit:Collection"))
        explicitColl = Usd.CollectionAPI.Apply(testPrim, 
                "test:Explicit:Collection")
        explicitColl.CreateExpansionRuleAttr(Usd.Tokens.explicitOnly)
                
        # The collection is initially empty.
        self.assertTrue(explicitColl.HasNoIncludedPaths())
        self.assertTrue('CollectionAPI:test:Explicit:Collection' in
                         testPrim.GetAppliedSchemas())
        self.assertTrue(testPrim.HasAPI(Usd.CollectionAPI))
        self.assertTrue(testPrim.HasAPI(Usd.CollectionAPI, 
            instanceName="test:Explicit:Collection"))
        self.assertTrue(not testPrim.HasAPI(Usd.CollectionAPI, 
            instanceName="unknown"))
        self.assertTrue(not testPrim.HasAPI(Usd.CollectionAPI, 
            instanceName="test"))

        self.assertEqual(explicitColl.GetCollectionPath(), 
                         Usd.CollectionAPI.GetNamedCollectionPath(testPrim, 
                            "test:Explicit:Collection"))
        # Verify the attribute representing the collection is found at the
        # collection path.
        self.assertEqual(
            explicitColl.GetCollectionAttr(),
            testPrim.GetAttributeAtPath(explicitColl.GetCollectionPath()))
        self.assertTrue(explicitColl.GetCollectionAttr().IsDefined())
        self.assertFalse(explicitColl.GetCollectionAttr().IsAuthored())
        self.assertFalse(explicitColl.GetCollectionAttr().HasValue())
        # Verify CreateCollectionAttr works and "authors" the attribute even 
        # though the attribute is opaque and can never have a value.
        self.assertTrue(explicitColl.CreateCollectionAttr())
        self.assertTrue(explicitColl.GetCollectionAttr().IsDefined())
        self.assertTrue(explicitColl.GetCollectionAttr().IsAuthored())
        self.assertFalse(explicitColl.GetCollectionAttr().HasValue())

        explicitColl.CreateIncludesRel().AddTarget(sphere.GetPath())
        self.assertFalse(explicitColl.HasNoIncludedPaths())

        explicitColl.GetIncludesRel().AddTarget(cube.GetPath())
        explicitColl.GetIncludesRel().AddTarget(cylinder.GetPath())
        explicitColl.GetIncludesRel().AddTarget(cone.GetPath())

        explicitCollMquery = explicitColl.ComputeMembershipQuery()
        self.checkQuery(explicitCollMquery, stage)

        explicitCollIncObjects = Usd.CollectionAPI.ComputeIncludedObjects(
                explicitCollMquery, stage)
        self.assertEqual(len(explicitCollIncObjects), 4)
        self.assertTrue(len(explicitCollMquery.GetAsPathExpansionRuleMap()) > 0)

        for obj in explicitCollIncObjects:
            self.assertTrue(explicitCollMquery.IsPathIncluded(obj.GetPath()))

        # Ensure that descendants of explicitly included objects aren't 
        # included in the collection.
        self.assertFalse(explicitCollMquery.IsPathIncluded(hemiSphere1.GetPath()))
        self.assertFalse(explicitCollMquery.IsPathIncluded(hemiSphere2.GetPath()))

        # An explicitly included object can be explicitly excluded from the 
        # collection. i.e. excludes is stronger than includes.
        explicitColl.CreateExcludesRel().AddTarget(cone.GetPath())

        # We have to recompute the membership map if we add or remove 
        # includes/excludes targets.
        explicitCollMquery = explicitColl.ComputeMembershipQuery()
        self.checkQuery(explicitCollMquery, stage)

        # Ensure that the cone is excluded.
        self.assertFalse(explicitCollMquery.IsPathIncluded(cone.GetPath()))

        # ----------------------------------------------------------
        # Test an expandPrims collection.
        self.assertTrue(Usd.CollectionAPI.CanApply(testPrim, 
                "testExpandPrimsColl"))
        expandPrimsColl = Usd.CollectionAPI.Apply(testPrim, 
                "testExpandPrimsColl")
        expandPrimsColl.CreateIncludesRel().AddTarget(geom.GetPath())
        self.assertTrue(expandPrimsColl.IsInRelationshipsMode())
        expandPrimsCollMquery = expandPrimsColl.ComputeMembershipQuery()
        self.checkQuery(expandPrimsCollMquery, stage)
        
        expandPrimCollIncObjects = Usd.CollectionAPI.ComputeIncludedObjects(
                expandPrimsCollMquery, stage)
        self.assertEqual(len(expandPrimCollIncObjects), 9)

        for obj in expandPrimCollIncObjects:
            self.assertTrue(expandPrimsCollMquery.IsPathIncluded(obj.GetPath()))

        # Exclude all shapes from the collection. This leaves just the instanced 
        # box behind.
        expandPrimsColl.CreateExcludesRel().AddTarget(shapes.GetPath())

        # Verify that there's no harm in excluding a path that isn't 
        # included.
        expandPrimsColl.GetExcludesRel().AddTarget(
            Sdf.Path("/Collection/Materials/Plastic"))

        expandPrimsCollMquery = expandPrimsColl.ComputeMembershipQuery()
        self.checkQuery(expandPrimsCollMquery, stage)
        expandPrimCollIncObjects = Usd.CollectionAPI.ComputeIncludedObjects(
                expandPrimsCollMquery, stage, Usd.TraverseInstanceProxies())
        self.assertEqual(len(expandPrimCollIncObjects), 4)

        # ----------------------------------------------------------
        # Test an expandPrimsAndProperties collection.
        self.assertTrue(Usd.CollectionAPI.CanApply(testPrim, 
                "testExpandPrimsAndPropertiesColl"))
        expandPrimsAndPropertiesColl = Usd.CollectionAPI.Apply(
                testPrim, 
                "testExpandPrimsAndPropertiesColl")
        expandPrimsAndPropertiesColl.CreateExpansionRuleAttr(
                Usd.Tokens.expandPrimsAndProperties)
        expandPrimsAndPropertiesColl.CreateIncludesRel().AddTarget(
                shapes.GetPath())
        self.assertTrue(expandPrimsAndPropertiesColl.IsInRelationshipsMode())
        expandPnPCollMquery = expandPrimsAndPropertiesColl.ComputeMembershipQuery()
        self.checkQuery(expandPnPCollMquery, stage)
        expandPnPCollObjects = Usd.CollectionAPI.ComputeIncludedObjects(
                expandPnPCollMquery, stage)

        self.assertEqual(len(expandPnPCollObjects), 21)
        for obj in expandPnPCollObjects:
            self.assertTrue(expandPnPCollMquery.IsPathIncluded(obj.GetPath()))

        # ----------------------------------------------------------
        # Test a collection that includes other collections. 
        # 
        # Create a collection that combines the explicit collection and 
        # the expandPrimsAndProperties collection.
        self.assertTrue(Usd.CollectionAPI.CanApply(testPrim, "combined"))
        combinedColl = Usd.CollectionAPI.Apply(testPrim, "combined")
        combinedColl.CreateExpansionRuleAttr(Usd.Tokens.explicitOnly)
        combinedColl.CreateIncludesRel().AddTarget(
            expandPrimsAndPropertiesColl.GetCollectionPath())
        combinedColl.CreateIncludesRel().AddTarget(
            explicitColl.GetCollectionPath())
        self.assertTrue(combinedColl.IsInRelationshipsMode())

        combinedMquery = combinedColl.ComputeMembershipQuery()
        self.checkQuery(combinedMquery, stage)

        combinedCollIncObjects = Usd.CollectionAPI.ComputeIncludedObjects(
                combinedMquery, stage)

        for obj in combinedCollIncObjects:
            self.assertTrue(combinedMquery.IsPathIncluded(obj.GetPath()))

        self.assertEqual(len(combinedCollIncObjects), 18)

        # now add the collection "expandPrimsColl", which includes "Geom" and 
        # exludes "Shapes", but is weaker than the "expandPrimsAndProperties" 
        # collection.
        combinedColl.CreateIncludesRel().AddTarget(
            expandPrimsColl.GetCollectionPath(),
            position=Usd.ListPositionBackOfAppendList)
        combinedMquery = combinedColl.ComputeMembershipQuery()
        self.checkQuery(combinedMquery, stage)
        combinedCollIncObjects = Usd.CollectionAPI.ComputeIncludedObjects(
                combinedMquery, stage)

        for obj in combinedCollIncObjects:
            self.assertTrue(combinedMquery.IsPathIncluded(obj.GetPath()))
        self.assertEqual(len(combinedCollIncObjects), 5)

        expandPrimsColl.ResetCollection()
        self.assertTrue(expandPrimsColl.HasNoIncludedPaths())
        
        explicitColl.BlockCollection()
        self.assertTrue(explicitColl.HasNoIncludedPaths())

    def test_testIncludeAndExcludePath(self):
        self.assertTrue(Usd.CollectionAPI.CanApply(geom, "geom"))
        geomCollection = Usd.CollectionAPI.Apply(geom, 
            "geom")
        self.assertTrue(geomCollection.IncludePath(shapes.GetPath()))
        self.assertTrue(geomCollection.ExcludePath(sphere.GetPath()))
        self.assertTrue(geomCollection.IsInRelationshipsMode())

        query = geomCollection.ComputeMembershipQuery()
        self.checkQuery(query, stage)
        self.assertTrue(query.IsPathIncluded(cylinder.GetPath()))
        self.assertTrue(query.IsPathIncluded(cube.GetPath()))
        self.assertFalse(query.IsPathIncluded(sphere.GetPath()))
        self.assertFalse(query.IsPathIncluded(hemiSphere1.GetPath()))
        self.assertFalse(query.IsPathIncluded(hemiSphere2.GetPath()))

        # Add just hemiSphere2
        self.assertTrue(geomCollection.IncludePath(hemiSphere2.GetPath()))

        # Remove hemiSphere1. Note that this does nothing however since it's 
        # not included in the collection.
        self.assertTrue(geomCollection.ExcludePath(hemiSphere1.GetPath()))

        # Every time we call IncludePath() or ExcludePath(), we must recompute 
        # the MembershipQuery object.
        query = geomCollection.ComputeMembershipQuery()
        self.checkQuery(query, stage)
        self.assertFalse(query.IsPathIncluded(sphere.GetPath()))
        self.assertFalse(query.IsPathIncluded(hemiSphere1.GetPath()))
        self.assertTrue(query.IsPathIncluded(hemiSphere2.GetPath()))

        # Add back sphere and verify that everything is included now.
        self.assertTrue(geomCollection.IncludePath(sphere.GetPath()))

        query = geomCollection.ComputeMembershipQuery()
        self.checkQuery(query, stage)
        self.assertTrue(query.IsPathIncluded(sphere.GetPath()))
        self.assertTrue(query.IsPathIncluded(hemiSphere1.GetPath()))
        self.assertTrue(query.IsPathIncluded(hemiSphere2.GetPath()))
        self.assertTrue(query.IsPathIncluded(cylinder.GetPath()))
        self.assertTrue(query.IsPathIncluded(cube.GetPath()))

        # Test includeRoot.
        # First create a collection that excludes /CollectionTest/Geom
        # but includes the root.
        self.assertTrue(Usd.CollectionAPI.CanApply(testPrim, "includeRootTest"))
        includeRootTest = Usd.CollectionAPI.Apply(testPrim,
            "includeRootTest")
        includeRootTest.IncludePath('/')
        includeRootTest.ExcludePath(geom.GetPath())
        query = includeRootTest.ComputeMembershipQuery()
        self.checkQuery(query, stage)
        self.assertTrue(query.IsPathIncluded(testPrim.GetPath()))
        self.assertFalse(query.IsPathIncluded(geom.GetPath()))
        self.assertFalse(query.IsPathIncluded(box.GetPath()))
        self.assertTrue(query.IsPathIncluded(materials.GetPath()))
        # Modify it to include /CollectionTest/Geom/Box,
        # a path under the excluded Geom scope.
        includeRootTest.IncludePath(box.GetPath())
        query = includeRootTest.ComputeMembershipQuery()
        self.checkQuery(query, stage)
        self.assertTrue(query.IsPathIncluded(testPrim.GetPath()))
        self.assertFalse(query.IsPathIncluded(geom.GetPath()))
        self.assertTrue(query.IsPathIncluded(box.GetPath()))
        self.assertTrue(query.IsPathIncluded(materials.GetPath()))

    def test_testReadCollection(self):
        leafGeom = Usd.CollectionAPI(testPrim, "leafGeom")
        self.assertTrue(leafGeom.IsInRelationshipsMode())
        (valid, reason) = leafGeom.Validate()
        self.assertTrue(valid)

        # Test the other overload of GetCollection.
        leafGeomPath = leafGeom.GetCollectionPath()
        leafGeom = Usd.CollectionAPI.Get(stage, leafGeomPath)
        self.assertEqual(leafGeom.GetCollectionPath(), leafGeomPath)

        (valid, reason) = leafGeom.Validate()
        self.assertTrue(valid)

        # Test GetName() API.
        self.assertEqual(leafGeom.GetName(), 'leafGeom')
        self.assertFalse(Usd.CollectionAPI.CanContainPropertyName(
            leafGeom.GetName()))
        self.assertTrue(leafGeom.GetCollectionPath().name)

        # Test Get/IsCollectionAPIPath API.
        self.assertTrue(Usd.CollectionAPI.IsCollectionAPIPath(
            leafGeom.GetCollectionPath()))

        # Ensure that paths of collection schema properties aren't valid
        # collection paths.
        self.assertFalse(Usd.CollectionAPI.IsCollectionAPIPath(
            leafGeom.GetExpansionRuleAttr().GetPath()))
        self.assertFalse(Usd.CollectionAPI.IsCollectionAPIPath(
            leafGeom.GetIncludesRel().GetPath()))

        leafGeomMquery = leafGeom.ComputeMembershipQuery()
        self.checkQuery(leafGeomMquery, stage)
        self.assertEqual(leafGeomMquery.GetIncludedCollections(), [])
        self.assertEqual(
            len(Usd.CollectionAPI.ComputeIncludedObjects(leafGeomMquery,
                                                         stage)),
            2)

        # Calling Apply on an already existing collection will not update
        # the expansionRule.
        self.assertEqual(leafGeom.GetExpansionRuleAttr().Get(), 
                         Usd.Tokens.explicitOnly)
        self.assertTrue(Usd.CollectionAPI.CanApply(testPrim, "leafGeom"))
        leafGeom = Usd.CollectionAPI.Apply(testPrim, "leafGeom")
        self.assertEqual(leafGeom.GetExpansionRuleAttr().Get(), 
                         Usd.Tokens.explicitOnly)

        allGeom = Usd.CollectionAPI(testPrim, "allGeom")
        (valid, reason) = allGeom.Validate()
        allGeomMquery = allGeom.ComputeMembershipQuery()
        self.checkQuery(allGeomMquery, stage)
        self.assertEqual(allGeomMquery.GetIncludedCollections(), [])
        self.assertEqual(len(Usd.CollectionAPI.ComputeIncludedObjects(
                allGeomMquery,stage)), 9)

        # included object count increases when we count instance proxies.
        self.assertEqual(len(Usd.CollectionAPI.ComputeIncludedObjects(
                allGeomMquery,stage,
                predicate=Usd.TraverseInstanceProxies())), 11)
    
        allGeomProperties = Usd.CollectionAPI(testPrim, "allGeomProperties")
        (valid, reason) = allGeomProperties.Validate()
        allGeomPropertiesMquery = allGeomProperties.ComputeMembershipQuery()
        self.checkQuery(allGeomPropertiesMquery, stage)
        self.assertEqual(allGeomPropertiesMquery.GetIncludedCollections(), [])
        self.assertEqual(len(Usd.CollectionAPI.ComputeIncludedObjects(
                allGeomPropertiesMquery, stage)), 33)

        hasRels = Usd.CollectionAPI(testPrim, "hasRelationships")
        (valid, reason) = hasRels.Validate()
        self.assertTrue(valid)
        hasRelsMquery = hasRels.ComputeMembershipQuery()
        self.checkQuery(hasRelsMquery, stage)
        self.assertEqual(hasRelsMquery.GetIncludedCollections(), [])
        incObjects = Usd.CollectionAPI.ComputeIncludedObjects(hasRelsMquery, stage)
        for obj in incObjects: 
            self.assertTrue(isinstance(obj, Usd.Property))

        hasInstanceProxy = Usd.CollectionAPI(testPrim, "hasInstanceProxy")
        (valid, reason) = hasInstanceProxy.Validate()
        self.assertTrue(valid)
        hasInstanceProxyMquery = hasInstanceProxy.ComputeMembershipQuery()
        self.checkQuery(hasInstanceProxyMquery, stage)
        self.assertEqual(hasInstanceProxyMquery.GetIncludedCollections(), [])
        incObjects = Usd.CollectionAPI.ComputeIncludedObjects(
                hasInstanceProxyMquery, stage)
        self.assertEqual(len(incObjects), 2)
        for obj in incObjects:
            self.assertTrue(obj.IsInstanceProxy())
            self.assertFalse(obj.IsInPrototype())
        
        coneProperties = Usd.CollectionAPI(testPrim, "coneProperties")
        (valid, reason) = coneProperties.Validate()
        self.assertTrue(valid)
        conePropertiesMquery = coneProperties.ComputeMembershipQuery()
        self.checkQuery(conePropertiesMquery, stage)
        self.assertEqual(conePropertiesMquery.GetIncludedCollections(), [])
        incObjects = Usd.CollectionAPI.ComputeIncludedObjects(
                conePropertiesMquery, stage)
        self.assertEqual(len(incObjects), 2)
        for obj in incObjects:
            self.assertTrue(isinstance(obj, Usd.Property))

        includesCollection = Usd.CollectionAPI(testPrim, "includesCollection")
        (valid, reason) = includesCollection.Validate()
        self.assertTrue(valid)
        includesCollectionMquery = includesCollection.ComputeMembershipQuery()
        self.checkQuery(includesCollectionMquery, stage)
        self.assertEqual(
            set(includesCollectionMquery.GetIncludedCollections()),
            set([Sdf.Path("/CollectionTest/Geom/Shapes.collection:allShapes")]))
        incObjects = Usd.CollectionAPI.ComputeIncludedObjects(
                includesCollectionMquery, stage)
        self.assertTrue(hemiSphere2 in incObjects)
        self.assertTrue(hemiSphere1 not in incObjects)

        includesNestedCollection = Usd.CollectionAPI(
            testPrim, "includesNestedCollection")
        (valid, reason) = includesNestedCollection.Validate()
        self.assertTrue(valid)
        includesNestedCollectionMquery = \
            includesNestedCollection.ComputeMembershipQuery()
        self.checkQuery(includesNestedCollectionMquery, stage)
        self.assertEqual(
            set(includesNestedCollectionMquery.GetIncludedCollections()),
            set([Sdf.Path("/CollectionTest/Geom/Shapes.collection:allShapes"),
                 Sdf.Path("/CollectionTest/Geom.collection:allGeom")]))

        excludeInstanceGeom = Usd.CollectionAPI(testPrim, "excludeInstanceGeom")
        (valid, reason) = excludeInstanceGeom.Validate()
        self.assertTrue(valid)
        excludeInstanceGeomMquery = excludeInstanceGeom.ComputeMembershipQuery()
        self.checkQuery(excludeInstanceGeomMquery, stage)
        self.assertEqual(excludeInstanceGeomMquery.GetIncludedCollections(), [])
        incObjects = Usd.CollectionAPI.ComputeIncludedObjects(
                excludeInstanceGeomMquery, stage)
        self.assertEqual(len(incObjects), 1)

        allIncObjects = Usd.CollectionAPI.ComputeIncludedObjects(
                excludeInstanceGeomMquery, stage, 
                predicate=Usd.TraverseInstanceProxies())
        self.assertEqual(len(allIncObjects), 2)

    def test_invalidCollections(self):
        invalidCollectionNames = ["invalidExpansionRule", 
            "invalidExcludesExplicitOnly",
            "invalidExcludesExpandPrims",
            "invalidTopLevelRules"]

        for collName in invalidCollectionNames:
            coll = Usd.CollectionAPI(testPrim, collName)
            (valid, reason) = coll.Validate()
            self.assertFalse(valid)
            self.assertTrue(len(reason) > 0)

    def test_CircularDependency(self):
        self.assertTrue(Usd.CollectionAPI.CanApply(testPrim, "A"))
        self.assertTrue(Usd.CollectionAPI.CanApply(testPrim, "B"))
        self.assertTrue(Usd.CollectionAPI.CanApply(testPrim, "C"))
        self.assertTrue(Usd.CollectionAPI.CanApply(testPrim, "D"))
        collectionA = Usd.CollectionAPI.Apply(testPrim, "A")
        collectionA.CreateExpansionRuleAttr(Usd.Tokens.explicitOnly)
        collectionB = Usd.CollectionAPI.Apply(testPrim, 
                "B")
        collectionC = Usd.CollectionAPI.Apply(testPrim, 
                "C")

        collectionD = Usd.CollectionAPI.Apply(testPrim, 
                "D")
                
        collectionA.CreateIncludesRel().AddTarget(
                collectionB.GetCollectionPath())
        collectionB.CreateIncludesRel().AddTarget(
                collectionC.GetCollectionPath())
        collectionC.CreateIncludesRel().AddTarget(
                collectionA.GetCollectionPath())
        
        collectionD.CreateIncludesRel().AddTarget(geom.GetPath())

        ComputeIncObjs = Usd.CollectionAPI.ComputeIncludedObjects

        # XXX: It would be good to verify that this produces a warning.
        (valid, reason) = collectionA.Validate()
        self.assertFalse(valid)
        self.assertTrue('circular' in reason)
        mqueryA = collectionA.ComputeMembershipQuery()
        self.checkQuery(mqueryA, stage)
        self.assertEqual(len(ComputeIncObjs(mqueryA, stage)), 0)
        self.assertEqual(mqueryA.GetIncludedCollections(),
                         [collectionB.GetCollectionPath(),
                          collectionC.GetCollectionPath()])

        (valid, reason) = collectionB.Validate()
        self.assertFalse(valid)
        self.assertTrue('circular' in reason)
        mqueryB = collectionB.ComputeMembershipQuery()
        self.checkQuery(mqueryB, stage)
        self.assertEqual(len(ComputeIncObjs(mqueryB, stage)), 0)
        self.assertEqual(mqueryB.GetIncludedCollections(),
                         [collectionA.GetCollectionPath(),
                          collectionC.GetCollectionPath()])

        (valid, reason) = collectionC.Validate()
        self.assertFalse(valid)
        self.assertTrue('circular' in reason)
        mqueryC = collectionC.ComputeMembershipQuery()
        self.checkQuery(mqueryC, stage)
        self.assertEqual(len(ComputeIncObjs(mqueryC, stage)), 0)
        self.assertEqual(mqueryC.GetIncludedCollections(),
                         [collectionA.GetCollectionPath(),
                          collectionB.GetCollectionPath()])

        # Now, if A includes D, the warning about circular dependency should 
        # not prevent inclusion of D in A, B or C.
        collectionA.CreateIncludesRel().AddTarget(
            collectionD.GetCollectionPath())
        mqueryA = collectionA.ComputeMembershipQuery()
        self.checkQuery(mqueryA, stage)
        self.assertEqual(len(ComputeIncObjs(mqueryA, stage)), 9)
        self.assertEqual(mqueryA.GetIncludedCollections(),
                         [collectionB.GetCollectionPath(),
                          collectionC.GetCollectionPath(),
                          collectionD.GetCollectionPath()])

        mqueryB = collectionB.ComputeMembershipQuery()
        self.checkQuery(mqueryB, stage)
        self.assertEqual(len(ComputeIncObjs(mqueryB, stage)), 9)
        self.assertEqual(mqueryB.GetIncludedCollections(),
                         [collectionA.GetCollectionPath(),
                          collectionC.GetCollectionPath(),
                          collectionD.GetCollectionPath()])

        mqueryC = collectionC.ComputeMembershipQuery()
        self.checkQuery(mqueryC, stage)
        self.assertEqual(len(ComputeIncObjs(mqueryC, stage)), 9)
        self.assertEqual(mqueryC.GetIncludedCollections(),
                         [collectionA.GetCollectionPath(),
                          collectionB.GetCollectionPath(),
                          collectionD.GetCollectionPath()])

        collectionA.CreateIncludesRel().RemoveTarget(
            collectionD.GetCollectionPath())

        # Test cycle detection where A includes B includes C includes B.
        collectionC.CreateIncludesRel().ClearTargets(False)
        collectionC.CreateIncludesRel().AddTarget(
            collectionB.GetCollectionPath())

        (valid, reason) = collectionA.Validate()
        self.assertFalse(valid)
        self.assertTrue('circular' in reason)
        mqueryA = collectionA.ComputeMembershipQuery()
        self.checkQuery(mqueryA, stage)
        self.assertEqual(len(ComputeIncObjs(mqueryA, stage)), 0)
        self.assertEqual(mqueryA.GetIncludedCollections(),
                         [collectionB.GetCollectionPath(),
                          collectionC.GetCollectionPath()])

        (valid, reason) = collectionB.Validate()
        self.assertFalse(valid)
        self.assertTrue('circular' in reason)
        mqueryB = collectionB.ComputeMembershipQuery()
        self.checkQuery(mqueryB, stage)
        self.assertEqual(len(ComputeIncObjs(mqueryB, stage)), 0)
        self.assertEqual(mqueryB.GetIncludedCollections(),
                         [collectionC.GetCollectionPath()])

        (valid, reason) = collectionC.Validate()
        self.assertFalse(valid)
        self.assertTrue('circular' in reason)
        mqueryC = collectionC.ComputeMembershipQuery()
        self.checkQuery(mqueryC, stage)
        self.assertEqual(len(ComputeIncObjs(mqueryC, stage)), 0)
        self.assertEqual(mqueryC.GetIncludedCollections(),
                         [collectionB.GetCollectionPath()])

        # Test cycle detection where A includes B includes B
        collectionB.CreateIncludesRel().ClearTargets(False)
        collectionB.CreateIncludesRel().AddTarget(
            collectionB.GetCollectionPath())

        (valid, reason) = collectionA.Validate()
        self.assertFalse(valid)
        self.assertTrue('circular' in reason)
        mqueryA = collectionA.ComputeMembershipQuery()
        self.checkQuery(mqueryA, stage)
        self.assertEqual(len(ComputeIncObjs(mqueryA, stage)), 0)
        self.assertEqual(mqueryA.GetIncludedCollections(),
                         [collectionB.GetCollectionPath()])

        (valid, reason) = collectionB.Validate()
        self.assertFalse(valid)
        self.assertTrue('circular' in reason)
        mqueryB = collectionB.ComputeMembershipQuery()
        self.checkQuery(mqueryB, stage)
        self.assertEqual(len(ComputeIncObjs(mqueryB, stage)), 0)
        self.assertEqual(mqueryB.GetIncludedCollections(), 
                         [])

        # Test cycle detection where A includes A
        collectionA.CreateIncludesRel().ClearTargets(False)
        collectionA.CreateIncludesRel().AddTarget(
            collectionA.GetCollectionPath())

        (valid, reason) = collectionA.Validate()
        self.assertFalse(valid)
        self.assertTrue('circular' in reason)
        mqueryA = collectionA.ComputeMembershipQuery()
        self.checkQuery(mqueryA, stage)
        self.assertEqual(len(ComputeIncObjs(mqueryA, stage)), 0)
        self.assertEqual(mqueryA.GetIncludedCollections(),
                         [])

    def test_InvalidApply(self):
        # ----------------------------------------------------------
        # Test Apply when passed a string that doesn't tokenize to
        # make sure we don't crash in that case, but issue a coding error.
        # Both CanApply and Apply raise coding errors in the instance name is 
        # empty.
        with self.assertRaises(Tf.ErrorException):
            self.assertFalse(Usd.CollectionAPI.CanApply(testPrim, ""))
        with self.assertRaises(Tf.ErrorException):
            Usd.CollectionAPI.Apply(testPrim, "")

        # Test Apply when the instance name is invalid because it matches a
        # property name. CanApply will return false, but the apply will still
        # occur as we don't enforce CanApply during Apply.
        self.assertFalse(Usd.CollectionAPI.CanApply(testPrim, "excludes"))
        self.assertTrue(Usd.CollectionAPI.Apply(testPrim, "excludes"))

    def test_CollectionEquivalence(self):
        # ----------------------------------------------------------
        # Test the ability to compare two collections whose MembershipQuery
        # ends up equivalent.

        # Get all collections on the root test prim
        collections = Usd.CollectionAPI.GetAll(testPrim)
        self.assertTrue(len(collections) > 1)

        # Each of their membership queries should be equal to itself, and
        # unequal to the others.  Same for their hashes -- although note that
        # the hashes are not, in general, guaranteed to be distinct due to the
        # pigeonhole principle.  Queries that do not use the rule map (i.e. they
        # use a membershipExpression) do not compare or hash equal.
        mqueries = [c.ComputeMembershipQuery() for c in collections]
        mqueries = [q for q in mqueries if q.UsesPathExpansionRuleMap()]
        for i in range(len(mqueries)):
            for j in range(i, len(mqueries)):
                if i == j:
                    self.assertEqual(mqueries[i], mqueries[j])
                    self.assertEqual(hash(mqueries[i]), hash(mqueries[j]))
                else:
                    self.assertNotEqual(mqueries[i], mqueries[j])

        # Confirm that the hash operator lets us use python dicts
        mqueryToPath = {}
        for (coll,mquery) in zip(collections, mqueries):
            mqueryToPath[mquery] = coll.GetCollectionPath()
        self.assertEqual(len(mqueryToPath.keys()), len(mqueries))

    def test_SchemaPropertyBaseNames(self):
        self.assertTrue(Usd.CollectionAPI.IsSchemaPropertyBaseName(
                "includeRoot"))
        self.assertTrue(Usd.CollectionAPI.IsSchemaPropertyBaseName(
                "expansionRule"))
        self.assertTrue(Usd.CollectionAPI.IsSchemaPropertyBaseName(
                "includes"))
        self.assertTrue(Usd.CollectionAPI.IsSchemaPropertyBaseName(
                "excludes"))
        # CollectionAPI does define a property with an empty base name, i.e.
        # "collection:{collectionName}"
        self.assertTrue(Usd.CollectionAPI.IsSchemaPropertyBaseName(
                ""))
        # "collection" is the prefix, not the base name.
        self.assertFalse(Usd.CollectionAPI.IsSchemaPropertyBaseName(
                Usd.Tokens.collection))

    def test_GetSchemaAttributeNames(self):
        # Note that since CollectionAPI doesn't inherit from any API schemas,
        # passing True vs False for includeInherited doesn't make a difference.
        self.assertEqual(Usd.CollectionAPI.GetSchemaAttributeNames(),
                         ['collection:__INSTANCE_NAME__:expansionRule', 
                          'collection:__INSTANCE_NAME__:includeRoot',
                          'collection:__INSTANCE_NAME__:membershipExpression',
                          'collection:__INSTANCE_NAME__'])

        self.assertEqual(Usd.CollectionAPI.GetSchemaAttributeNames(False, ""),
                         ['collection:__INSTANCE_NAME__:expansionRule', 
                          'collection:__INSTANCE_NAME__:includeRoot',
                          'collection:__INSTANCE_NAME__:membershipExpression',
                          'collection:__INSTANCE_NAME__'])

        self.assertEqual(Usd.CollectionAPI.GetSchemaAttributeNames(True, ""),
                         ['collection:__INSTANCE_NAME__:expansionRule', 
                          'collection:__INSTANCE_NAME__:includeRoot',
                          'collection:__INSTANCE_NAME__:membershipExpression',
                          'collection:__INSTANCE_NAME__'])

        self.assertEqual(Usd.CollectionAPI.GetSchemaAttributeNames(False, "foo"),
                         ['collection:foo:expansionRule', 
                          'collection:foo:includeRoot',
                          'collection:foo:membershipExpression',
                          'collection:foo'])

        self.assertEqual(Usd.CollectionAPI.GetSchemaAttributeNames(True, "bar"),
                         ['collection:bar:expansionRule', 
                          'collection:bar:includeRoot',
                          'collection:bar:membershipExpression',
                          'collection:bar'])

    def test_RelativePathIsPathIncluded(self):
        # ----------------------------------------------------------
        # Test IsPathIncluded when passing in a relative path issues a coding
        # error.
        allGeomCollection = Usd.CollectionAPI.Get(testPrim, 'allGeom')
        query = allGeomCollection.ComputeMembershipQuery()
        with self.assertRaises(Tf.ErrorException):
            query.IsPathIncluded('CollectionTest/Geom')

        with self.assertRaises(Tf.ErrorException):
            query.IsPathIncluded('CollectionTest/Geom', Usd.Tokens.expandPrims)

    def test_ExplicitOnlyAndIncludeRoot(self):
        # Regression test that a membership query for a collection that has
        # includeRoot=true and expansionMode=explicitOnly does not trigger a
        # coding error.
        collection = Usd.CollectionAPI.Get(testPrim,
            'explicitOnlyAndIncludeRoot')
        query = collection.ComputeMembershipQuery()
        self.assertEqual(
            Usd.ComputeIncludedPathsFromCollection(query, stage), [])

    def test_MembershipExpressions(self):
        withMembershipExpr = Usd.CollectionAPI.Get(
            testPrim, 'withMembershipExpr')
        self.assertTrue(withMembershipExpr.IsInExpressionMode())

        query = withMembershipExpr.ComputeMembershipQuery()
        self.assertFalse(query.UsesPathExpansionRuleMap())

        self.assertEqual(
            Usd.ComputeIncludedPathsFromCollection(query, stage),
            [Sdf.Path('/CollectionTest'),
             Sdf.Path('/CollectionTest/Geom/Box'),
             Sdf.Path('/CollectionTest/Geom/Shapes/Cone'),
             Sdf.Path('/CollectionTest/Geom/Shapes/Cube'),
             Sdf.Path('/CollectionTest/Geom/Shapes/Cylinder'),
             Sdf.Path('/CollectionTest/Geom/Shapes/Sphere/Hemisphere1'),
             Sdf.Path('/CollectionTest/Geom/Shapes/Sphere/Hemisphere2')])

        # Test ResolveCompleteMembershipExpression.
        self.assertEqual(
            withMembershipExpr.ResolveCompleteMembershipExpression(),
            Sdf.PathExpression("/CollectionTest/Geom//C* //{model} //Box "
                               "/CollectionTest/Geom/Shapes//H*"))

        expressionRef = Usd.CollectionAPI.Get(
            testPrim, 'expressionRef') 
        query = expressionRef.ComputeMembershipQuery()
        self.assertFalse(query.UsesPathExpansionRuleMap())
        self.assertEqual(
            Usd.ComputeIncludedPathsFromCollection(query, stage),
            [Sdf.Path('/CollectionTest/Geom/Shapes/Sphere/Hemisphere1'),
             Sdf.Path('/CollectionTest/Geom/Shapes/Sphere/Hemisphere2')])

        # Test that `//` leading exprs translate across references.
        srcStage = Usd.Stage.CreateInMemory()
        dstStage = Usd.Stage.CreateInMemory()

        src = srcStage.DefinePrim('/src')
        dst = dstStage.DefinePrim('/dst')

        dstCapi = Usd.CollectionAPI.Apply(dst, 'testRef')
        dstCapi.GetMembershipExpressionAttr().Set(Sdf.PathExpression('//'))
        
        src.GetReferences().AddReference(
            dstStage.GetRootLayer().identifier, '/dst')

        srcCapi = Usd.CollectionAPI.Get(src, 'testRef')
        self.assertTrue(srcCapi)
        self.assertEqual(srcCapi.GetMembershipExpressionAttr().Get(),
                         Sdf.PathExpression('//'))

    def test_HashMembershipQuery(self):
        self.assertEqual(
            hash(Usd.UsdCollectionMembershipQuery()),
            hash(Usd.UsdCollectionMembershipQuery())
        )
        self.assertEqual(
            hash(Usd.CollectionAPI.Get(testPrim, 'allGeom').ComputeMembershipQuery()),
            hash(Usd.CollectionAPI.Get(testPrim, 'allGeom').ComputeMembershipQuery())
        )

    def test_ExpressionCyclesBlockAndReset(self):
        rootC = Usd.CollectionAPI.Get(testExprPrim, 'root')
        ref1C = Usd.CollectionAPI.Get(testExprPrim, 'ref1')
        ref2C = Usd.CollectionAPI.Get(testExprPrim, 'ref2')

        self.assertTrue(rootC)
        self.assertTrue(ref1C)
        self.assertTrue(ref2C)

        self.assertTrue(rootC.IsInExpressionMode())
        self.assertTrue(ref1C.IsInExpressionMode())
        self.assertTrue(ref2C.IsInExpressionMode())

        # root references ref1, ref1 references ref2, and ref2 references root
        # again, forming a cycle.  The expectation is that when a reference is
        # encountered a second time (and a cycle detected) then the empty
        # expression is substituted.  These calls emit expected warnings.
        self.assertEqual(
            rootC.ResolveCompleteMembershipExpression(),
            Sdf.PathExpression('/root (/ref1 /ref2) - /ref2'))

        self.assertEqual(
            ref1C.ResolveCompleteMembershipExpression(),
            Sdf.PathExpression('/ref1 (/ref2 /root)'))
        
        self.assertEqual(
            ref2C.ResolveCompleteMembershipExpression(),
            Sdf.PathExpression('/ref2 (/root /ref1)'))

        # Check that blocking 'ref2' leaves it with no possibility of included
        # paths, and that it breaks the cycle.
        with Usd.EditContext(stage, stage.GetSessionLayer()):
            self.assertTrue(ref2C.BlockCollection())

        self.assertTrue(ref2C.HasNoIncludedPaths())

        self.assertEqual(
            rootC.ResolveCompleteMembershipExpression(),
            Sdf.PathExpression('/root /ref1'))

        self.assertEqual(
            ref1C.ResolveCompleteMembershipExpression(),
            Sdf.PathExpression('/ref1'))
        
        self.assertEqual(
            ref2C.ResolveCompleteMembershipExpression(),
            Sdf.PathExpression())

        # Calling ResetCollection on the session layer should clear the block
        # and return us to the original state.
        with Usd.EditContext(stage, stage.GetSessionLayer()):
            self.assertTrue(ref2C.ResetCollection())

        self.assertEqual(
            rootC.ResolveCompleteMembershipExpression(),
            Sdf.PathExpression('/root (/ref1 /ref2) - /ref2'))

        self.assertEqual(
            ref1C.ResolveCompleteMembershipExpression(),
            Sdf.PathExpression('/ref1 (/ref2 /root)'))
        
        self.assertEqual(
            ref2C.ResolveCompleteMembershipExpression(),
            Sdf.PathExpression('/ref2 (/root /ref1)'))

        # Calling ResetCollection on the root layer should clear the opinion
        # for 'membershipExpression'.
        self.assertTrue(ref2C.ResetCollection())

        self.assertTrue(ref2C.HasNoIncludedPaths())

        self.assertEqual(
            rootC.ResolveCompleteMembershipExpression(),
            Sdf.PathExpression('/root /ref1'))

        self.assertEqual(
            ref1C.ResolveCompleteMembershipExpression(),
            Sdf.PathExpression('/ref1'))
        
        self.assertEqual(
            ref2C.ResolveCompleteMembershipExpression(),
            Sdf.PathExpression())
        

if __name__ == "__main__":
    unittest.main()
