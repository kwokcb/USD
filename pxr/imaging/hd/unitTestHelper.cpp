//
// Copyright 2016 Pixar
//
// Licensed under the terms set forth in the LICENSE.txt file available at
// https://openusd.org/license.
//
#include "pxr/imaging/hd/unitTestHelper.h"
#include "pxr/imaging/hd/camera.h"
#include "pxr/imaging/hd/rprimCollection.h"
#include "pxr/imaging/hd/tokens.h"
#include "pxr/imaging/hd/unitTestNullRenderPass.h"

#include "pxr/base/gf/camera.h"
#include "pxr/base/gf/matrix4d.h"
#include "pxr/base/gf/frustum.h"
#include "pxr/base/tf/getenv.h"
#include "pxr/base/tf/staticTokens.h"

#include <string>
#include <sstream>

PXR_NAMESPACE_OPEN_SCOPE


TF_DEFINE_PRIVATE_TOKENS(
    _tokens,
    (l0dir)
    (l0color)
    (l1dir)
    (l1color)
    (sceneAmbient)
    (vec3)

    // Collection names
    (testCollection)
);

class Hd_DrawTask final : public HdTask
{
public:
    Hd_DrawTask(HdRenderPassSharedPtr const &renderPass,
                HdRenderPassStateSharedPtr const &renderPassState,
                bool withGuides)
    : HdTask(SdfPath::EmptyPath())
    , _renderPass(renderPass)
    , _renderPassState(renderPassState)
    , _renderTags()
    {
        _renderTags.reserve(2);
        _renderTags.push_back(HdRenderTagTokens->geometry);

        if (withGuides) {
            _renderTags.push_back(HdRenderTagTokens->guide);
        }
    }

    void Sync(HdSceneDelegate*, HdTaskContext*, HdDirtyBits*) override
    {
        _renderPass->Sync();
    }

    void Prepare(HdTaskContext* ctx, HdRenderIndex* renderIndex) override
    {
        _renderPassState->Prepare(renderIndex->GetResourceRegistry());
    }

    void Execute(HdTaskContext* ctx) override
    {
        _renderPass->Execute(_renderPassState, GetRenderTags());
    }

    const TfTokenVector &GetRenderTags() const override
    {
        return _renderTags;
    }

private:
    HdRenderPassSharedPtr _renderPass;
    HdRenderPassStateSharedPtr _renderPassState;
    TfTokenVector _renderTags;

    Hd_DrawTask() = delete;
    Hd_DrawTask(const Hd_DrawTask &) = delete;
    Hd_DrawTask &operator =(const Hd_DrawTask &) = delete;
};

template <typename T>
static VtArray<T>
_BuildArray(T values[], int numValues)
{
    VtArray<T> result(numValues);
    std::copy(values, values+numValues, result.begin());
    return result;
}

Hd_TestDriver::Hd_TestDriver()
 : _engine()
 , _renderDelegate()
 , _renderIndex(nullptr)
 , _sceneDelegate(nullptr)
 , _cameraId(SdfPath("/__camera"))
 , _renderPass()
 , _renderPassState(_renderDelegate.CreateRenderPassState())
 , _collection(_tokens->testCollection, HdReprSelector())
{
    HdReprSelector reprSelector = HdReprSelector(HdReprTokens->smoothHull);
    _Init(reprSelector);
}

Hd_TestDriver::Hd_TestDriver(HdReprSelector const &reprSelector)
 : _engine()
 , _renderDelegate()
 , _renderIndex(nullptr)
 , _sceneDelegate(nullptr)
 , _cameraId(SdfPath("/__camera"))
 , _renderPass()
 , _renderPassState(_renderDelegate.CreateRenderPassState())
 , _collection(_tokens->testCollection, HdReprSelector())
{
    _Init(reprSelector);
}

Hd_TestDriver::~Hd_TestDriver()
{
    delete _sceneDelegate;
    delete _renderIndex;
}

void
Hd_TestDriver::_Init(HdReprSelector const &reprSelector)
{
    _renderIndex = HdRenderIndex::New(&_renderDelegate, HdDriverVector());
    TF_VERIFY(_renderIndex != nullptr);

    _sceneDelegate = new HdUnitTestDelegate(_renderIndex,
                                             SdfPath::AbsoluteRootPath());

    _sceneDelegate->AddCamera(_cameraId);
    GfMatrix4d viewMatrix = GfMatrix4d().SetIdentity();
    viewMatrix *= GfMatrix4d().SetTranslate(GfVec3d(0.0, 1000.0, 0.0));
    viewMatrix *= GfMatrix4d().SetRotate(GfRotation(GfVec3d(1.0, 0.0, 0.0), -90.0));

    GfFrustum frustum;
    frustum.SetPerspective(45, true, 1, 1.0, 10000.0);
    GfMatrix4d projMatrix = frustum.ComputeProjectionMatrix();

    SetCamera(
        viewMatrix,
        projMatrix,
        CameraUtilFraming(
            GfRect2i(GfVec2i(0, 0), 512, 512)));

    // set depthfunc to default
    _renderPassState->SetDepthFunc(HdCmpFuncLess);

    // Update collection with repr and add collection to change tracker.
    _collection.SetReprSelector(reprSelector);
    HdChangeTracker &tracker = _renderIndex->GetChangeTracker();
    tracker.AddCollection(_collection.GetName());
}

void
Hd_TestDriver::Draw(bool withGuides)
{
    Draw(GetRenderPass(), withGuides);
}

void
Hd_TestDriver::Draw(HdRenderPassSharedPtr const &renderPass, bool withGuides)
{
    HdTaskSharedPtrVector tasks = {
        std::make_shared<Hd_DrawTask>(renderPass, _renderPassState, withGuides)
    };
    _engine.Execute(&_sceneDelegate->GetRenderIndex(), &tasks);
}

static
HdCamera::Projection
_ToHd(const GfCamera::Projection projection)
{
    switch(projection) {
    case GfCamera::Perspective:
        return HdCamera::Perspective;
    case GfCamera::Orthographic:
        return HdCamera::Orthographic;
    }
    TF_CODING_ERROR("Bad GfCamera::Projection value");
    return HdCamera::Perspective;
}

void
Hd_TestDriver::SetCamera(GfMatrix4d const &viewMatrix,
                         GfMatrix4d const &projectionMatrix,
                         CameraUtilFraming const &framing)
{
    GfCamera cam;
    cam.SetFromViewAndProjectionMatrix(viewMatrix,
                                       projectionMatrix);
    
    _sceneDelegate->UpdateTransform(
        _cameraId,
        GfMatrix4f(cam.GetTransform()));
    _sceneDelegate->UpdateCamera(
        _cameraId,
        HdCameraTokens->projection,
        VtValue(_ToHd(cam.GetProjection())));
    _sceneDelegate->UpdateCamera(
        _cameraId,
        HdCameraTokens->focalLength,
        VtValue(cam.GetFocalLength() *
                float(GfCamera::FOCAL_LENGTH_UNIT)));
    _sceneDelegate->UpdateCamera(
        _cameraId,
        HdCameraTokens->horizontalAperture,
        VtValue(cam.GetHorizontalAperture() *
                float(GfCamera::APERTURE_UNIT)));
    _sceneDelegate->UpdateCamera(
        _cameraId,
        HdCameraTokens->verticalAperture,
        VtValue(cam.GetVerticalAperture() *
                float(GfCamera::APERTURE_UNIT)));
    _sceneDelegate->UpdateCamera(
        _cameraId,
        HdCameraTokens->horizontalApertureOffset,
        VtValue(cam.GetHorizontalApertureOffset() *
                float(GfCamera::APERTURE_UNIT)));
    _sceneDelegate->UpdateCamera(
        _cameraId,
        HdCameraTokens->verticalApertureOffset,
        VtValue(cam.GetVerticalApertureOffset() *
                float(GfCamera::APERTURE_UNIT)));
    _sceneDelegate->UpdateCamera(
        _cameraId,
        HdCameraTokens->clippingRange,
        VtValue(cam.GetClippingRange()));

    // Baselines for tests were generated without constraining the view
    // frustum based on the viewport aspect ratio.
    _sceneDelegate->UpdateCamera(
        _cameraId, HdCameraTokens->windowPolicy,
        VtValue(CameraUtilDontConform));
    
    const HdCamera * const camera =
        dynamic_cast<HdCamera const *>(
            _renderIndex->GetSprim(
                HdPrimTypeTokens->camera,
                _cameraId));
    TF_VERIFY(camera);
    _renderPassState->SetCamera(camera);
    _renderPassState->SetFraming(framing);
    _renderPassState->SetOverrideWindowPolicy(std::nullopt);
}

void
Hd_TestDriver::SetCullStyle(HdCullStyle cullStyle)
{
    _renderPassState->SetCullStyle(cullStyle);
}

HdRenderPassSharedPtr const &
Hd_TestDriver::GetRenderPass()
{
    if (!_renderPass) {
        _renderPass = HdRenderPassSharedPtr(
            new Hd_UnitTestNullRenderPass(&_sceneDelegate->GetRenderIndex(),
                                          _collection));
    }
    return _renderPass;
}

void
Hd_TestDriver::SetRepr(HdReprSelector const &reprSelector)
{
    _collection.SetReprSelector(reprSelector);

    // Mark changes.
    HdChangeTracker &tracker = _renderIndex->GetChangeTracker();
    tracker.MarkCollectionDirty(_collection.GetName());

    // Update render pass with updated collection
    _renderPass->SetRprimCollection(_collection);
}

PXR_NAMESPACE_CLOSE_SCOPE

