# Frontend Integration Guide - MetaView Demo Enhancements

## 🎯 Quick Start

The backend now provides enhanced brand extraction and faster processing. Here's how to integrate it into the frontend.

---

## 📝 Step 1: Update API Client

**File**: `src/api/client.ts`

Add the new V2 endpoint function:

```typescript
// Add to existing client.ts

export interface BrandElements {
  brand_name?: string
  logo_base64?: string
  hero_image_base64?: string
  favicon_url?: string
}

export interface DemoPreviewResponseV2 extends DemoPreviewResponse {
  brand?: BrandElements
}

/**
 * Generate demo preview using optimized V2 endpoint.
 *
 * IMPROVEMENTS:
 * - 30-40% faster processing (~30s vs ~48s)
 * - Extracts brand logo, colors, hero image
 * - Better brand alignment
 */
export async function generateDemoPreviewV2(url: string): Promise<DemoPreviewResponseV2> {
  const response = await fetch(`${API_BASE_URL}/api/v1/demo-v2/preview`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ url }),
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to generate preview')
  }

  return response.json()
}
```

---

## 📝 Step 2: Update Demo Page

**File**: `src/pages/Demo.tsx`

### Option A: Switch to V2 Endpoint (Recommended)

```typescript
// Change import
import { generateDemoPreviewV2 as generateDemoPreview } from '../api/client'

// Rest of code stays the same!
// The response now includes brand elements
```

### Option B: Use V2 with Type Updates

```typescript
import { generateDemoPreviewV2, type DemoPreviewResponseV2 } from '../api/client'

// Update state type
const [preview, setPreview] = useState<DemoPreviewResponseV2 | null>(null)

// In handleSubmit
const result = await generateDemoPreviewV2(url)
setPreview(result)

// Now you can use brand elements!
if (preview?.brand?.logo_base64) {
  // Display brand logo
}
```

---

## 🎨 Step 3: Display Brand Elements

### Show Brand Logo

Add brand logo display in the preview section:

```tsx
{/* Brand Logo Display */}
{preview?.brand?.logo_base64 && (
  <div className="mb-6 flex items-center justify-center">
    <div className="relative p-4 bg-white rounded-xl shadow-sm border border-gray-100">
      <img
        src={`data:image/png;base64,${preview.brand.logo_base64}`}
        alt={preview.brand.brand_name || 'Brand logo'}
        className="h-12 w-auto object-contain"
        onError={(e) => {
          // Hide if logo fails to load
          e.currentTarget.style.display = 'none'
        }}
      />
    </div>
  </div>
)}
```

### Show Brand Name

```tsx
{/* Brand Name Badge */}
{preview?.brand?.brand_name && (
  <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-blue-50 border border-blue-100 rounded-full text-sm font-medium text-blue-700 mb-4">
    <SparklesIcon className="w-4 h-4" />
    <span>{preview.brand.brand_name}</span>
  </div>
)}
```

### Use Brand Colors

The colors are now automatically in `preview.blueprint`:

```tsx
{/* These colors are now brand-aligned! */}
<div
  style={{
    background: `linear-gradient(135deg, ${preview.blueprint.primary_color}, ${preview.blueprint.secondary_color})`,
  }}
  className="p-6 rounded-xl"
>
  {/* Content */}
</div>
```

---

## 📝 Step 4: Enhanced Social Previews

The `composited_preview_image_url` now includes brand elements. No changes needed - it just works better!

```tsx
{/* This now shows brand-aligned og:image */}
<img
  src={platformData.imageUrl}
  alt={platformData.title}
  className="w-full h-full object-cover"
/>

// where platformData.imageUrl = preview.composited_preview_image_url
```

---

## 🎯 Step 5: Update Progress UI (Optional Enhancement)

Update the progress stages to reflect actual backend processing:

```typescript
const stages = [
  {
    id: 1,
    name: 'Capturing Screenshot',
    icon: PhotoIcon,
    duration: 7, // Reduced from 8s
    description: 'Loading page and capturing high-quality screenshot'
  },
  {
    id: 2,
    name: 'Extracting Brand',
    icon: SparklesIcon,
    duration: 4, // NEW STAGE
    description: 'Detecting logo, colors, and brand elements'
  },
  {
    id: 3,
    name: 'AI Analysis',
    icon: SparklesIcon,
    duration: 25, // Slightly faster
    description: 'Running multi-stage reasoning'
  },
  {
    id: 4,
    name: 'Generating Preview',
    icon: PhotoIcon,
    duration: 5, // Faster
    description: 'Creating brand-aligned social preview'
  },
  {
    id: 5,
    name: 'Finalizing',
    icon: CheckIcon,
    duration: 2, // Much faster!
    description: 'Optimizing and caching'
  }
]

// Total: ~43s (progress bar) vs ~30s (actual)
// This gives buffer for variability
```

---

## 🧪 Testing Guide

### Test Cases

1. **Test with subpay.dk**
   ```
   - Should extract Subpay logo
   - Should get teal/green brand colors
   - Should complete in ~30s
   - Should show brand name "Subpay"
   ```

2. **Test with stripe.com**
   ```
   - Should extract Stripe logo
   - Should get purple brand colors
   - Should complete in ~30s
   ```

3. **Test with minimal site (example.com)**
   ```
   - Should fallback gracefully (no logo)
   - Should still work
   - Should complete in ~25s (less processing)
   ```

### Visual Checks

- [ ] Brand logo appears (if site has one)
- [ ] Colors match actual brand
- [ ] Social preview looks professional
- [ ] No broken images
- [ ] Progress completes smoothly
- [ ] Error handling works

---

## 🔄 Migration Strategy

### Phase 1: Testing (Week 1)
- Deploy backend changes
- Add V2 endpoint to API client
- Test with development environment
- Verify all features work

### Phase 2: Soft Launch (Week 2)
- Update Demo page to use V2
- Monitor performance metrics
- Collect user feedback
- Fix any edge cases

### Phase 3: Full Rollout (Week 3)
- Make V2 the default
- Update documentation
- Deprecation notice for V1
- Plan V1 sunset (optional)

### Phase 4: Cleanup (Week 4+)
- (Optional) Remove V1 endpoint
- Optimize based on metrics
- Add more enhancements

---

## 📊 What to Monitor

### Performance Metrics

```typescript
// Log processing time
console.log('Preview generated in:', preview.processing_time_ms, 'ms')

// Expected: ~30,000ms (30s) vs old ~48,000ms (48s)
```

### Brand Extraction Success

```typescript
// Track success rate
const hasBrandElements = !!(
  preview.brand?.logo_base64 ||
  preview.brand?.hero_image_base64 ||
  preview.brand?.brand_name
)

// Log for analytics
if (hasBrandElements) {
  console.log('✅ Brand extraction successful')
  // Track in analytics
}
```

### User Experience

- Time to first preview
- Bounce rate during loading
- Conversion rate (email signup)
- Social share rate

---

## 🎨 UI Enhancement Ideas

### 1. Brand Elements Showcase

Show extracted brand elements prominently:

```tsx
{preview?.brand && (
  <div className="p-6 bg-gradient-to-br from-blue-50 to-indigo-50 rounded-2xl border border-blue-100 mb-8">
    <div className="flex items-center gap-3 mb-4">
      <div className="p-2 bg-white rounded-lg">
        <SparklesIcon className="w-5 h-5 text-blue-600" />
      </div>
      <h3 className="text-lg font-semibold text-gray-900">
        Brand Elements Detected
      </h3>
    </div>

    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {/* Logo */}
      {preview.brand.logo_base64 && (
        <div className="flex flex-col items-center p-4 bg-white rounded-xl">
          <img
            src={`data:image/png;base64,${preview.brand.logo_base64}`}
            alt="Brand logo"
            className="h-16 w-auto mb-2"
          />
          <span className="text-xs text-gray-600">Logo</span>
        </div>
      )}

      {/* Colors */}
      <div className="flex flex-col items-center p-4 bg-white rounded-xl">
        <div className="flex gap-2 mb-2">
          <div
            className="w-8 h-8 rounded-full"
            style={{ background: preview.blueprint.primary_color }}
          />
          <div
            className="w-8 h-8 rounded-full"
            style={{ background: preview.blueprint.secondary_color }}
          />
          <div
            className="w-8 h-8 rounded-full"
            style={{ background: preview.blueprint.accent_color }}
          />
        </div>
        <span className="text-xs text-gray-600">Brand Colors</span>
      </div>

      {/* Brand Name */}
      {preview.brand.brand_name && (
        <div className="flex flex-col items-center justify-center p-4 bg-white rounded-xl">
          <span className="text-lg font-semibold text-gray-900 mb-1">
            {preview.brand.brand_name}
          </span>
          <span className="text-xs text-gray-600">Brand Name</span>
        </div>
      )}
    </div>
  </div>
)}
```

### 2. Processing Time Badge

Show processing time improvement:

```tsx
{preview && (
  <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-green-50 border border-green-200 rounded-full">
    <ClockIcon className="w-4 h-4 text-green-600" />
    <span className="text-sm font-medium text-green-700">
      Generated in {(preview.processing_time_ms / 1000).toFixed(1)}s
    </span>
    {preview.processing_time_ms < 35000 && (
      <span className="text-xs text-green-600">⚡ Fast</span>
    )}
  </div>
)}
```

### 3. Before/After Comparison

Show old vs new processing time:

```tsx
<div className="grid grid-cols-2 gap-4 p-4 bg-gray-50 rounded-xl">
  <div className="text-center">
    <div className="text-2xl font-bold text-gray-400 line-through">48s</div>
    <div className="text-xs text-gray-500">Old</div>
  </div>
  <div className="text-center">
    <div className="text-2xl font-bold text-green-600">
      {(preview.processing_time_ms / 1000).toFixed(0)}s
    </div>
    <div className="text-xs text-green-600">New ⚡</div>
  </div>
</div>
```

---

## 🐛 Common Issues & Solutions

### Issue: TypeScript errors with brand property

**Solution**: Update type imports

```typescript
import type { DemoPreviewResponseV2 } from '../api/client'
const [preview, setPreview] = useState<DemoPreviewResponseV2 | null>(null)
```

### Issue: Logo not displaying

**Cause**: Logo might be null or invalid base64

**Solution**: Always check before rendering

```typescript
{preview?.brand?.logo_base64 && (
  <img
    src={`data:image/png;base64,${preview.brand.logo_base64}`}
    onError={(e) => e.currentTarget.style.display = 'none'}
  />
)}
```

### Issue: Colors look wrong

**Cause**: Brand colors might not be extracted properly for all sites

**Solution**: Always have fallback

```typescript
const primaryColor = preview?.blueprint?.primary_color || '#2563EB'
```

---

## 📚 Complete Example

Here's a complete example of updated Demo.tsx with all enhancements:

```tsx
import { generateDemoPreviewV2, type DemoPreviewResponseV2 } from '../api/client'

export default function Demo() {
  const [preview, setPreview] = useState<DemoPreviewResponseV2 | null>(null)

  const handleSubmit = async () => {
    try {
      setIsGeneratingPreview(true)
      const result = await generateDemoPreviewV2(url)
      setPreview(result)

      // Log performance
      console.log(`✅ Generated in ${result.processing_time_ms}ms`)
      if (result.brand) {
        console.log(`✅ Brand extracted:`, result.brand.brand_name)
      }
    } catch (error) {
      console.error('Preview generation failed:', error)
      setPreviewError(error.message)
    } finally {
      setIsGeneratingPreview(false)
    }
  }

  return (
    <div>
      {/* ... existing UI ... */}

      {preview && (
        <>
          {/* Brand Elements Showcase */}
          {preview.brand && (
            <div className="mb-8">
              {/* Brand display code from above */}
            </div>
          )}

          {/* Reconstructed Preview */}
          <ReconstructedPreview preview={preview} />

          {/* Social Previews - now with better og:image */}
          <div className="mt-8">
            {/* Platform previews */}
          </div>
        </>
      )}
    </div>
  )
}
```

---

## ✅ Checklist for Integration

- [ ] Add `generateDemoPreviewV2` to API client
- [ ] Update type definitions
- [ ] Switch Demo.tsx to use V2 endpoint
- [ ] Add brand element display (logo, colors, name)
- [ ] Update progress stages
- [ ] Test with multiple URLs
- [ ] Monitor processing times
- [ ] Collect user feedback
- [ ] Deploy to production

---

**Ready to integrate? The backend is deployed and waiting!** 🚀

**Questions?** Check the main documentation in `METAVIEW_DEMO_ENHANCEMENTS.md`
