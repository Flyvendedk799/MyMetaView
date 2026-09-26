import React, { useState, useRef, useEffect } from 'react';
import type { Preview } from '../api/types';
import PlatformPreviewCard from './PlatformPreviewCard';

/**
 * EDITMODE DEFAULTS
 */
const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "accentColor": "#6366f1",
  "density": 1,
  "defaultDevice": "mobile",
  "defaultPlatform": "twitter",
  "animationPreset": "floatingWave",
  "enableFloorGrid": true
}/*EDITMODE-END*/;

// Embedded self-contained CSS styles
const EMBEDDED_CSS = `
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
}

body, html {
  width: 100%;
  height: 100%;
  background: #09090b;
  color: #f4f4f5;
  overflow: hidden;
}

/* Custom Scrollbar */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.02);
}
::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.15);
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.3);
}

/* 3D Motion Keyframe Animations */
@keyframes floatingWave {
  0% { transform: translateY(0px) rotateX(0deg) rotateY(0deg); }
  50% { transform: translateY(-16px) rotateX(3deg) rotateY(-3deg); }
  100% { transform: translateY(0px) rotateX(0deg) rotateY(0deg); }
}

@keyframes turntableOrbit {
  0% { transform: rotateY(0deg); }
  100% { transform: rotateY(360deg); }
}

@keyframes pulseElevate {
  0% { transform: scale(1) translateZ(0px); filter: drop-shadow(0 20px 30px rgba(0,0,0,0.5)); }
  50% { transform: scale(1.03) translateZ(30px); filter: drop-shadow(0 35px 50px rgba(99, 102, 241, 0.4)); }
  100% { transform: scale(1) translateZ(0px); filter: drop-shadow(0 20px 30px rgba(0,0,0,0.5)); }
}

.anim-floatingWave {
  animation: floatingWave 6s ease-in-out infinite;
}
.anim-turntableOrbit {
  animation: turntableOrbit 12s linear infinite;
}
.anim-pulseElevate {
  animation: pulseElevate 4s ease-in-out infinite;
}

/* 3D Floor Grid Pattern */
.perspective-stage {
  perspective: 1200px;
  transform-style: preserve-3d;
}

.floor-grid {
  position: absolute;
  width: 2000px;
  height: 2000px;
  top: 50%;
  left: 50%;
  margin-top: -1000px;
  margin-left: -1000px;
  background-image: 
    linear-gradient(to right, rgba(255, 255, 255, 0.05) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(255, 255, 255, 0.05) 1px, transparent 1px);
  background-size: 40px 40px;
  transform: rotateX(80deg) translateZ(-350px);
  pointer-events: none;
  opacity: 0.6;
  mask-image: radial-gradient(circle at 50% 50%, black 20%, transparent 70%);
}

.glass-panel {
  background: rgba(18, 18, 24, 0.75);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.tweak-btn {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #d4d4d8;
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  gap: 6px;
}
.tweak-btn:hover {
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  border-color: rgba(255, 255, 255, 0.25);
}
.tweak-btn.active {
  background: var(--ocd-accent, #6366f1);
  color: #fff;
  border-color: transparent;
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.35);
}

.preset-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.preset-card:hover {
  background: rgba(255, 255, 255, 0.07);
  border-color: rgba(255, 255, 255, 0.2);
  transform: translateY(-1px);
}
.preset-card.active {
  border-color: var(--ocd-accent, #6366f1);
  background: rgba(99, 102, 241, 0.12);
  box-shadow: 0 0 15px rgba(99, 102, 241, 0.2);
}
`;

// Inline Styles Object Defined BEFORE App component
const styles: Record<string, React.CSSProperties> = {
  appContainer: {
    display: "flex",
    flexDirection: "column",
    background: "#09090b",
    color: "#f4f4f5",
    overflow: "hidden"
  },
  topHeader: {
    height: "56px",
    background: "rgba(18, 18, 24, 0.9)",
    backdropFilter: "blur(16px)",
    borderBottom: "1px solid rgba(255, 255, 255, 0.1)",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0 16px",
    zIndex: 20
  },
  logoBadge: {
    background: "linear-gradient(135deg, #6366f1, #a855f7)",
    color: "#fff",
    fontWeight: "900",
    fontSize: "12px",
    padding: "4px 8px",
    borderRadius: "6px",
    boxShadow: "0 2px 10px rgba(99, 102, 241, 0.4)"
  },
  segmentedControl: {
    display: "flex",
    alignItems: "center",
    gap: "4px",
    background: "rgba(255, 255, 255, 0.03)",
    padding: "4px",
    borderRadius: "10px",
    border: "1px solid rgba(255, 255, 255, 0.08)"
  },
  mainWorkspace: {
    flex: 1,
    display: "flex",
    overflow: "hidden",
    position: "relative"
  },
  controlDrawer: {
    width: "320px",
    height: "100%",
    overflowY: "auto",
    padding: "16px",
    display: "flex",
    flexDirection: "column",
    gap: "18px",
    zIndex: 10,
    borderRight: "1px solid rgba(255, 255, 255, 0.1)"
  },
  drawerSection: {
    borderBottom: "1px solid rgba(255, 255, 255, 0.06)",
    paddingBottom: "14px"
  },
  sectionLabel: {
    fontSize: "10px",
    fontWeight: "800",
    color: "#71717a",
    letterSpacing: "0.08em"
  },
  inputLabel: {
    fontSize: "11px",
    fontWeight: "600",
    color: "#a1a1aa",
    marginBottom: "4px",
    display: "block"
  },
  textInput: {
    width: "100%",
    background: "rgba(255, 255, 255, 0.05)",
    border: "1px solid rgba(255, 255, 255, 0.12)",
    borderRadius: "8px",
    padding: "8px 10px",
    color: "#fff",
    fontSize: "12px",
    outline: "none"
  },
  canvasStage: {
    flex: 1,
    height: "100%",
    position: "relative",
    overflow: "hidden",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    cursor: "grab",
    userSelect: "none"
  },
  canvasHUD: {
    position: "absolute",
    top: "16px",
    left: "16px",
    right: "16px",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    zIndex: 15,
    pointerEvents: "auto"
  },
  hudBadge: {
    background: "rgba(0, 0, 0, 0.6)",
    border: "1px solid rgba(255, 255, 255, 0.1)",
    backdropFilter: "blur(8px)",
    padding: "3px 8px",
    borderRadius: "6px",
    fontSize: "10px",
    fontWeight: "700",
    color: "#d4d4d8"
  },
  perspectiveStageContainer: {
    width: "100%",
    height: "100%",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    transformStyle: "preserve-3d"
  },

  // MOBILE DEVICE STYLES (iPhone 16 Pro)
  mobileFrame: {
    width: "360px",
    height: "720px",
    background: "#000000",
    borderRadius: "44px",
    border: "10px solid #1c1c1e",
    boxShadow: "0 25px 60px rgba(0, 0, 0, 0.8), inset 0 0 0 2px rgba(255,255,255,0.15)",
    display: "flex",
    flexDirection: "column",
    position: "relative",
    overflow: "hidden",
    transformStyle: "preserve-3d"
  },
  mobileNotchBar: {
    height: "36px",
    padding: "0 18px",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    zIndex: 10
  },
  dynamicIsland: {
    width: "90px",
    height: "22px",
    background: "#000",
    borderRadius: "12px",
    border: "1px solid rgba(255, 255, 255, 0.1)"
  },
  mobileAppHeader: {
    height: "40px",
    padding: "0 12px",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    borderBottom: "1px solid rgba(255,255,255,0.06)",
    background: "rgba(10,10,12,0.8)"
  },
  mobileStoriesRow: {
    display: "flex",
    gap: "10px",
    padding: "8px 12px",
    overflowX: "hidden",
    borderBottom: "1px solid rgba(255,255,255,0.06)",
    background: "#000"
  },
  storyItem: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "4px"
  },
  storyRing: {
    width: "42px",
    height: "42px",
    borderRadius: "50%",
    padding: "2px",
    position: "relative"
  },
  storyAvatar: {
    width: "100%",
    height: "100%",
    borderRadius: "50%",
    background: "#3f3f46",
    color: "#fff",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontWeight: "bold",
    fontSize: "12px"
  },
  storyAddBadge: {
    position: "absolute",
    bottom: "-2px",
    right: "-2px",
    background: "#3b82f6",
    color: "#fff",
    borderRadius: "50%",
    width: "14px",
    height: "14px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "10px",
    fontWeight: "bold",
    border: "1px solid #000"
  },
  storyLabel: {
    fontSize: "9px",
    color: "#a1a1aa",
    maxWidth: "42px",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap"
  },
  mobileFeedScroll: {
    flex: 1,
    width: "100%",
    overflowY: "auto",
    display: "flex",
    flexDirection: "column"
  },
  mobileSecondaryPost: {
    background: "rgba(255,255,255,0.03)",
    margin: "0 8px 12px 8px",
    padding: "10px",
    borderRadius: "12px",
    border: "1px solid rgba(255,255,255,0.06)"
  },
  mobileBottomNav: {
    height: "44px",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-around",
    borderTop: "1px solid rgba(255,255,255,0.08)",
    background: "#000"
  },
  mobileHomeBar: {
    width: "120px",
    height: "4px",
    background: "#ffffff",
    borderRadius: "2px",
    margin: "4px auto 6px auto"
  },

  // LAPTOP DEVICE STYLES (MacBook Pro 16")
  laptopWrapper: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    transformStyle: "preserve-3d"
  },
  laptopScreen: {
    width: "840px",
    height: "520px",
    background: "#0c0c0e",
    borderRadius: "16px 16px 0 0",
    border: "8px solid #1c1c1e",
    borderBottom: "none",
    boxShadow: "0 25px 60px rgba(0, 0, 0, 0.8)",
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
    position: "relative"
  },
  webcamDot: {
    width: "6px",
    height: "6px",
    background: "#000",
    borderRadius: "50%",
    margin: "4px auto 2px auto",
    border: "1px solid #333"
  },
  browserHeader: {
    height: "30px",
    background: "#18181b",
    borderBottom: "1px solid rgba(255,255,255,0.08)",
    display: "flex",
    alignItems: "center",
    padding: "0 10px",
    gap: "10px"
  },
  urlBar: {
    flex: 1,
    background: "rgba(255,255,255,0.05)",
    borderRadius: "6px",
    padding: "3px 10px",
    fontSize: "10px",
    color: "#a1a1aa",
    textAlign: "center"
  },
  laptopAppBody: {
    flex: 1,
    display: "flex",
    overflow: "hidden"
  },
  laptopNavColumn: {
    width: "160px",
    background: "#09090b",
    borderRight: "1px solid rgba(255,255,255,0.08)",
    padding: "8px",
    display: "flex",
    flexDirection: "column",
    gap: "4px"
  },
  laptopNavItemActive: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    padding: "6px 10px",
    borderRadius: "8px",
    background: "rgba(255,255,255,0.1)",
    color: "#fff",
    fontSize: "11px",
    fontWeight: "700"
  },
  laptopNavItem: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    padding: "6px 10px",
    borderRadius: "8px",
    color: "#a1a1aa",
    fontSize: "11px",
    fontWeight: "500"
  },
  laptopPostBtn: {
    marginTop: "auto",
    color: "#fff",
    border: "none",
    borderRadius: "8px",
    padding: "8px",
    fontWeight: "700",
    fontSize: "11px",
    cursor: "pointer"
  },
  laptopCenterFeed: {
    flex: 1,
    overflowY: "auto",
    padding: "10px",
    display: "flex",
    flexDirection: "column"
  },
  laptopComposerCard: {
    background: "rgba(255,255,255,0.03)",
    border: "1px solid rgba(255,255,255,0.06)",
    borderRadius: "10px",
    padding: "8px 10px",
    marginBottom: "10px"
  },
  laptopRepliesContainer: {
    background: "rgba(255,255,255,0.03)",
    borderRadius: "10px",
    padding: "8px 10px",
    border: "1px solid rgba(255,255,255,0.06)"
  },
  laptopRightSidebar: {
    width: "180px",
    background: "#09090b",
    borderLeft: "1px solid rgba(255,255,255,0.08)",
    padding: "8px",
    display: "flex",
    flexDirection: "column",
    gap: "8px"
  },
  laptopSearchInput: {
    background: "rgba(255,255,255,0.05)",
    borderRadius: "8px",
    padding: "6px 8px",
    display: "flex",
    alignItems: "center",
    gap: "6px",
    fontSize: "10px"
  },
  laptopWidgetCard: {
    background: "rgba(255,255,255,0.03)",
    borderRadius: "8px",
    padding: "8px",
    border: "1px solid rgba(255,255,255,0.06)"
  },
  laptopBase: {
    width: "920px",
    height: "14px",
    background: "linear-gradient(to bottom, #27272a, #18181b)",
    borderRadius: "0 0 16px 16px",
    boxShadow: "0 10px 20px rgba(0,0,0,0.5)",
    position: "relative"
  },
  thumbNotch: {
    width: "70px",
    height: "4px",
    background: "#09090b",
    borderRadius: "0 0 4px 4px",
    margin: "0 auto"
  },

  // DESKTOP DEVICE STYLES (32" Studio Display)
  desktopWrapper: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    transformStyle: "preserve-3d"
  },
  desktopMonitor: {
    width: "960px",
    height: "560px",
    background: "#09090b",
    borderRadius: "12px",
    border: "8px solid #27272a",
    boxShadow: "0 30px 80px rgba(0, 0, 0, 0.9)",
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
    position: "relative"
  },
  desktopHeader: {
    height: "28px",
    background: "#18181b",
    borderBottom: "1px solid rgba(255,255,255,0.08)",
    display: "flex",
    alignItems: "center",
    padding: "0 10px",
    gap: "10px"
  },
  desktopAppBody: {
    flex: 1,
    display: "flex",
    overflow: "hidden"
  },
  desktopNavRail: {
    width: "160px",
    background: "#0e0e12",
    borderRight: "1px solid rgba(255,255,255,0.08)",
    display: "flex",
    flexDirection: "column"
  },
  desktopNavItemActive: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    padding: "6px 8px",
    borderRadius: "6px",
    background: "rgba(255,255,255,0.1)",
    color: "#fff",
    fontSize: "10px",
    fontWeight: "700",
    marginBottom: "4px"
  },
  desktopNavItem: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    padding: "6px 8px",
    borderRadius: "6px",
    color: "#a1a1aa",
    fontSize: "10px",
    fontWeight: "500",
    marginBottom: "4px"
  },
  desktopCenterCanvas: {
    flex: 1,
    overflowY: "auto",
    padding: "12px",
    display: "flex",
    flexDirection: "column",
    background: "#09090b"
  },
  desktopWorkspaceBanner: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    background: "rgba(255,255,255,0.03)",
    padding: "8px 12px",
    borderRadius: "8px",
    border: "1px solid rgba(255,255,255,0.06)",
    marginBottom: "8px"
  },
  desktopBannerBtnActive: {
    color: "#fff",
    border: "none",
    padding: "4px 10px",
    borderRadius: "6px",
    fontSize: "10px",
    fontWeight: "700",
    cursor: "pointer"
  },
  desktopMetricsRow: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr 1fr",
    gap: "8px",
    marginTop: "8px"
  },
  desktopMetricCard: {
    background: "rgba(255,255,255,0.03)",
    border: "1px solid rgba(255,255,255,0.06)",
    borderRadius: "8px",
    padding: "6px 8px",
    display: "flex",
    flexDirection: "column"
  },
  desktopInspectorPanel: {
    width: "160px",
    background: "#0e0e12",
    borderLeft: "1px solid rgba(255,255,255,0.08)",
    padding: "10px",
    display: "flex",
    flexDirection: "column",
    gap: "8px"
  },
  inspectorWidget: {
    background: "rgba(255,255,255,0.03)",
    border: "1px solid rgba(255,255,255,0.06)",
    borderRadius: "6px",
    padding: "6px 8px"
  },
  desktopStandNeck: {
    width: "100px",
    height: "50px",
    background: "linear-gradient(to bottom, #3f3f46, #27272a)",
    clipPath: "polygon(25% 0%, 75% 0%, 100% 100%, 0% 100%)"
  },
  desktopStandBase: {
    width: "240px",
    height: "8px",
    background: "#3f3f46",
    borderRadius: "4px",
    boxShadow: "0 10px 20px rgba(0,0,0,0.5)"
  }
};

export default function SpatialPreviewStudio({ preview }: { preview?: any }) {
  const [isFullscreen, setIsFullscreen] = useState(false);
  // Platform & Viewport Selection
  const [platform, setPlatform] = useState(TWEAK_DEFAULTS.defaultPlatform);
  const [device, setDevice] = useState(TWEAK_DEFAULTS.defaultDevice);

  // 3D Spatial Orientation State
  const [pitch, setPitch] = useState(20);
  const [yaw, setYaw] = useState(-20);
  const [roll, setRoll] = useState(0);
  const [zoom, setZoom] = useState(1.0);
  const [anglePreset, setAnglePreset] = useState("isometric");

  // 3D Motion Animations
  const [animationPreset, setAnimationPreset] = useState(TWEAK_DEFAULTS.animationPreset);
  const [animationSpeed, setAnimationSpeed] = useState("normal");
  const [isPlaying, setIsPlaying] = useState(true);

  // Studio Display Toggles
  const [enableFloorGrid, setEnableFloorGrid] = useState(TWEAK_DEFAULTS.enableFloorGrid);
  const [enableGlassBorder, setEnableGlassBorder] = useState(true);
  const [layerElevation, setLayerElevation] = useState(25);

  // Post Content Customization
  const [authorName, setAuthorName] = useState(preview?.brand?.brand_name || preview?.domain || "Alex Rivera");
  const [authorHandle, setAuthorHandle] = useState(
    preview?.domain ? preview.domain.split('.')[0] : "alexrivera_ui"
  );
  const [postCaption, setPostCaption] = useState(
    preview?.description || preview?.title || "Building spatial 2.5D interfaces in React! Drag with mouse to orbit 360°, inspect depth layers, and preview post fidelity across mobile, laptop, & desktop views. ✨ #SpatialUI #DesignSystems"
  );
  const [postTimestamp, setPostTimestamp] = useState("2h ago");
  const [likeCount, setLikeCount] = useState("4.8K");
  const [repostCount, setRepostCount] = useState("1.2K");
  const [commentCount, setCommentCount] = useState("342");
  const [viewCount, setViewCount] = useState("98.4K");
  const [mediaType, setMediaType] = useState("single"); // "single", "grid", "video", "poll"
  const [isVerified, setIsVerified] = useState(true);
  const [pollVotedOption, setPollVotedOption] = useState(0);

  // Mouse Orbit Drag Logic
  const canvasRef = useRef<HTMLElement>(null);
  const isDragging = useRef(false);
  const startPos = useRef({ x: 0, y: 0 });
  const startAngles = useRef({ pitch: 20, yaw: -20, roll: 0 });

  // Angle Presets Map
  const applyAnglePreset = (presetKey) => {
    setAnglePreset(presetKey);
    switch (presetKey) {
      case "isometric":
        setPitch(25); setYaw(-25); setRoll(0); break;
      case "hero":
        setPitch(15); setYaw(-12); setRoll(3); break;
      case "tiltRight":
        setPitch(18); setYaw(30); setRoll(0); break;
      case "tiltLeft":
        setPitch(18); setYaw(-30); setRoll(0); break;
      case "topDown":
        setPitch(65); setYaw(0); setRoll(0); break;
      case "flat":
        setPitch(0); setYaw(0); setRoll(0); break;
      default:
        break;
    }
  };

  // Pointer Down Drag Initialization
  const handlePointerDown = (e) => {
    if (e.target.closest("button") || e.target.closest("input") || e.target.closest("textarea") || e.target.closest(".control-drawer")) return;
    isDragging.current = true;
    startPos.current = { x: e.clientX, y: e.clientY };
    startAngles.current = { pitch, yaw, roll };
    setAnglePreset("custom");
  };

  // Pointer Move Drag Update
  const handlePointerMove = (e) => {
    if (!isDragging.current) return;
    const deltaX = e.clientX - startPos.current.x;
    const deltaY = e.clientY - startPos.current.y;

    if (e.shiftKey) {
      // Adjust Roll with Shift + Drag X
      const newRoll = Math.max(-45, Math.min(45, startAngles.current.roll + deltaX * 0.3));
      setRoll(Math.round(newRoll));
    } else {
      // Adjust Pitch & Yaw
      const newYaw = (startAngles.current.yaw + deltaX * 0.4) % 360;
      const newPitch = Math.max(-80, Math.min(80, startAngles.current.pitch - deltaY * 0.4));
      setYaw(Math.round(newYaw));
      setPitch(Math.round(newPitch));
    }
  };

  const handlePointerUp = () => {
    isDragging.current = false;
  };

  // Non-passive Wheel Listener for Smooth Canvas Zoom
  useEffect(() => {
    const canvasEl = canvasRef.current;
    if (!canvasEl) return;

    const handleWheel = (e) => {
      e.preventDefault();
      setZoom((prevZoom) => {
        const delta = e.deltaY > 0 ? -0.05 : 0.05;
        return Math.max(0.5, Math.min(2.0, parseFloat((prevZoom + delta).toFixed(2))));
      });
    };

    canvasEl.addEventListener("wheel", handleWheel, { passive: false });
    return () => canvasEl.removeEventListener("wheel", handleWheel);
  }, []);

  // Platform Branding Configs
  const platformConfigs = {
    twitter: {
      name: "X / Twitter",
      icon: "𝕏",
      accent: "#1d9bf0",
      cardBg: "#000000",
      border: "rgba(255, 255, 255, 0.15)",
      handlePrefix: "@"
    },
    linkedin: {
      name: "LinkedIn",
      icon: "in",
      accent: "#0a66c2",
      cardBg: "#1b1f23",
      border: "rgba(255, 255, 255, 0.12)",
      handlePrefix: "in/"
    },
    instagram: {
      name: "Instagram",
      icon: "📸",
      accent: "#e1306c",
      cardBg: "#121212",
      border: "rgba(255, 255, 255, 0.16)",
      handlePrefix: ""
    },
    tiktok: {
      name: "TikTok",
      icon: "🎵",
      accent: "#fe2c55",
      cardBg: "#121212",
      border: "rgba(255, 255, 255, 0.16)",
      handlePrefix: "@"
    }
  };

  const platformConfig = platformConfigs[platform as keyof typeof platformConfigs] || platformConfigs.twitter;

  // Render High-Fidelity 2.5D Social Media Post Card
  const renderPostCard = () => {
    return (
      <div
        style={{
          width: "100%",
          maxWidth: "100%",
          background: platformConfig.cardBg,
          borderRadius: "16px",
          border: enableGlassBorder
            ? `1px solid ${platformConfig.border}`
            : "none",
          boxShadow: "0 20px 40px rgba(0, 0, 0, 0.5)",
          padding: "16px",
          color: "#ffffff",
          transformStyle: "preserve-3d",
          position: "relative"
        }}
      >
        {/* Parallax Layer 1: Post Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: "12px",
            transform: `translateZ(${layerElevation * 0.4}px)`,
            transition: "transform 0.2s ease"
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div
              style={{
                width: "44px",
                height: "44px",
                borderRadius: "50%",
                background: `linear-gradient(135deg, ${platformConfig.accent}, #a855f7)`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontWeight: "bold",
                fontSize: "18px",
                color: "#fff",
                boxShadow: `0 4px 12px ${platformConfig.accent}40`,
                border: "2px solid rgba(255,255,255,0.2)"
              }}
            >
              {authorName.charAt(0)}
            </div>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                <span style={{ fontWeight: "700", fontSize: "14px", color: "#fff" }}>
                  {authorName}
                </span>
                {isVerified && (
                  <span
                    style={{
                      color: platformConfig.accent,
                      fontSize: "13px"
                    }}
                    title="Verified Profile"
                  >
                    ☑
                  </span>
                )}
              </div>
              <span style={{ fontSize: "12px", color: "#a1a1aa" }}>
                {platformConfig.handlePrefix}{authorHandle} • {postTimestamp}
              </span>
            </div>
          </div>
          <span style={{ color: "#71717a", fontSize: "16px", cursor: "pointer" }}>•••</span>
        </div>

        {/* Parallax Layer 2: Caption Text */}
        <p
          style={{
            fontSize: "13px",
            lineHeight: "1.5",
            color: "#e4e4e7",
            marginBottom: "14px",
            wordBreak: "break-word",
            transform: `translateZ(${layerElevation * 0.7}px)`,
            transition: "transform 0.2s ease"
          }}
        >
          {postCaption}
        </p>

        {/* Parallax Layer 3: Dynamic Media Attachment */}
        <div
          style={{
            borderRadius: "12px",
            overflow: "hidden",
            marginBottom: "14px",
            transform: `translateZ(${layerElevation * 1.3}px)`,
            boxShadow: "0 12px 28px rgba(0,0,0,0.6)",
            border: "1px solid rgba(255,255,255,0.1)",
            background: "#09090b",
            transition: "transform 0.2s ease"
          }}
        >
          {mediaType === "single" && (
            preview?.composited_preview_image_url ? (
              <img 
                src={preview.composited_preview_image_url} 
                alt="Generated Preview" 
                style={{ width: "100%", height: "auto", display: "block" }} 
              />
            ) : (
              <div
                style={{
                  height: "200px",
                  background: `linear-gradient(135deg, #1e1b4b 0%, #311b92 50%, ${platformConfig.accent} 100%)`,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  position: "relative",
                  padding: "20px"
                }}
              >
                <div style={{ fontSize: "36px", marginBottom: "8px" }}>🎨</div>
                <span style={{ fontWeight: "700", fontSize: "15px", color: "#fff" }}>Spatial Design Showcase</span>
                <span style={{ fontSize: "12px", color: "rgba(255,255,255,0.7)" }}>High Resolution 2.5D Render</span>
              </div>
            )
          )}

          {mediaType === "grid" && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "2px", height: "200px" }}>
              <div style={{ background: "linear-gradient(135deg, #4c1d95, #7c3aed)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "24px" }}>📐</div>
              <div style={{ background: "linear-gradient(135deg, #065f46, #059669)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "24px" }}>💡</div>
              <div style={{ background: "linear-gradient(135deg, #1e3a8a, #2563eb)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "24px" }}>🚀</div>
              <div style={{ background: "linear-gradient(135deg, #831843, #db2777)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "24px" }}>⚡</div>
            </div>
          )}

          {mediaType === "video" && (
            <div style={{ height: "200px", background: "#050508", position: "relative", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <div style={{ width: "52px", height: "52px", borderRadius: "50%", background: platformConfig.accent, display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "0 0 20px rgba(0,0,0,0.6)", fontSize: "20px", paddingLeft: "4px" }}>
                ▶
              </div>
              <div style={{ position: "absolute", bottom: "10px", left: "10px", right: "10px", display: "flex", alignItems: "center", gap: "8px", background: "rgba(0,0,0,0.6)", padding: "4px 8px", borderRadius: "6px" }}>
                <span style={{ fontSize: "10px", color: "#fff" }}>0:42 / 2:15</span>
                <div style={{ flex: 1, height: "4px", background: "rgba(255,255,255,0.2)", borderRadius: "2px", overflow: "hidden" }}>
                  <div style={{ width: "35%", height: "100%", background: platformConfig.accent }} />
                </div>
              </div>
            </div>
          )}

          {mediaType === "poll" && (
            <div style={{ padding: "16px", background: "#18181b" }}>
              <span style={{ fontSize: "12px", fontWeight: "700", color: "#a1a1aa", display: "block", marginBottom: "10px" }}>
                COMMUNITY POLL • 1,482 VOTES
              </span>
              {[
                { title: "React & 2.5D CSS", percent: 64 },
                { title: "Three.js / WebGL", percent: 26 },
                { title: "Canvas 2D", percent: 10 }
              ].map((opt, idx) => (
                <div
                  key={opt.title}
                  onClick={() => setPollVotedOption(idx)}
                  style={{
                    position: "relative",
                    background: "rgba(255,255,255,0.05)",
                    borderRadius: "8px",
                    padding: "10px 12px",
                    marginBottom: "8px",
                    cursor: "pointer",
                    overflow: "hidden",
                    border: pollVotedOption === idx ? `1px solid ${platformConfig.accent}` : "1px solid transparent"
                  }}
                >
                  <div
                    style={{
                      position: "absolute",
                      left: 0,
                      top: 0,
                      bottom: 0,
                      width: `${opt.percent}%`,
                      background: pollVotedOption === idx ? `${platformConfig.accent}40` : "rgba(255,255,255,0.08)",
                      transition: "width 0.4s ease"
                    }}
                  />
                  <div style={{ position: "relative", display: "flex", justifyContent: "space-between", fontSize: "12px", fontWeight: "600" }}>
                    <span>{opt.title} {pollVotedOption === idx && "✓"}</span>
                    <span>{opt.percent}%</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Parallax Layer 4: Engagement Actions Footer */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            paddingTop: "10px",
            borderTop: "1px solid rgba(255, 255, 255, 0.08)",
            fontSize: "12px",
            color: "#a1a1aa",
            transform: `translateZ(${layerElevation * 0.9}px)`,
            transition: "transform 0.2s ease"
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
            <span style={{ display: "flex", alignItems: "center", gap: "4px", cursor: "pointer" }}>
              💬 <span>{commentCount}</span>
            </span>
            <span style={{ display: "flex", alignItems: "center", gap: "4px", cursor: "pointer" }}>
              🔁 <span>{repostCount}</span>
            </span>
            <span style={{ display: "flex", alignItems: "center", gap: "4px", color: platformConfig.accent, cursor: "pointer" }}>
              ❤️ <span>{likeCount}</span>
            </span>
            <span style={{ display: "flex", alignItems: "center", gap: "4px", cursor: "pointer" }}>
              📊 <span>{viewCount}</span>
            </span>
          </div>
          <span style={{ cursor: "pointer" }}>🔖</span>
        </div>
      </div>
    );
  };

  // Render Devices (Mobile, Laptop, Desktop) Filled 100% Edge-To-Edge
  const renderDevice = () => {
    if (device === "mobile") {
      return (
        <div style={styles.mobileFrame}>
          {/* Top iOS Notch Bar */}
          <div style={styles.mobileNotchBar}>
            <span style={{ fontSize: "11px", fontWeight: "600", color: "#fff" }}>9:41</span>
            <div style={styles.dynamicIsland} />
            <span style={{ fontSize: "10px", color: "#fff" }}>📶 5G 🔋</span>
          </div>

          {/* Platform Mobile Header */}
          <div style={styles.mobileAppHeader}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ fontSize: "16px" }}>{platformConfig.icon}</span>
              <span style={{ fontSize: "14px", fontWeight: "700", color: "#fff" }}>
                {platformConfig.name}
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "12px", color: "#a1a1aa", fontSize: "14px" }}>
              <span>🔍</span>
              <span>🔔</span>
              <span>✈️</span>
            </div>
          </div>

          {/* Stories Highlights Carousel */}
          <div style={styles.mobileStoriesRow}>
            <div style={styles.storyItem}>
              <div style={{ ...styles.storyRing, border: `2px solid ${platformConfig.accent}` }}>
                <div style={styles.storyAvatar}>{authorName.charAt(0)}</div>
                <div style={styles.storyAddBadge}>+</div>
              </div>
              <span style={styles.storyLabel}>Your story</span>
            </div>
            {["Alex", "Sarah", "DesignLab", "TechPulse", "Elena"].map((name, i) => (
              <div key={name} style={styles.storyItem}>
                <div style={{ ...styles.storyRing, border: `2px solid ${i % 2 === 0 ? platformConfig.accent : "rgba(255,255,255,0.2)"}` }}>
                  <div style={{ ...styles.storyAvatar, background: `hsl(${i * 65 + 160}, 65%, 45%)` }}>
                    {name.charAt(0)}
                  </div>
                </div>
                <span style={styles.storyLabel}>{name}</span>
              </div>
            ))}
          </div>

          {/* Mobile Feed Area Spanning Edge-to-Edge */}
          <div style={styles.mobileFeedScroll}>
            {/* Focal 2.5D Active Post Card */}
            <div style={{ width: "100%", padding: "4px 8px 12px 8px" }}>
              {renderPostCard()}
            </div>

            {/* Secondary Post Item in Stream for Realism */}
            <div style={styles.mobileSecondaryPost}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
                <div style={{ width: "28px", height: "28px", borderRadius: "50%", background: "#3b82f6", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontWeight: "bold", fontSize: "11px" }}>
                  T
                </div>
                <div>
                  <span style={{ fontSize: "11px", fontWeight: "700", color: "#e2e8f0" }}>Tech Pulse</span>
                  <span style={{ fontSize: "10px", color: "#64748b", marginLeft: "4px" }}>• 4h ago</span>
                </div>
              </div>
              <p style={{ fontSize: "11px", color: "#94a3b8", lineHeight: "1.4", margin: 0 }}>
                Exploring spatial UI depth tokens & real-time viewport perspective in 2026. What's your stack? 🚀
              </p>
            </div>
          </div>

          {/* Mobile Bottom Navigation */}
          <div style={styles.mobileBottomNav}>
            <span style={{ color: platformConfig.accent, fontSize: "16px" }}>🏠</span>
            <span style={{ fontSize: "16px" }}>🔍</span>
            <span style={{ background: platformConfig.accent, width: "28px", height: "22px", borderRadius: "6px", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontWeight: "bold", fontSize: "14px" }}>+</span>
            <span style={{ fontSize: "16px" }}>🎬</span>
            <span style={{ fontSize: "16px" }}>👤</span>
          </div>

          {/* iOS Home Bar */}
          <div style={styles.mobileHomeBar} />
        </div>
      );
    }

    if (device === "laptop") {
      return (
        <div style={styles.laptopWrapper}>
          <div style={styles.laptopScreen}>
            {/* Webcam */}
            <div style={styles.webcamDot} />

            {/* Browser Header Bar */}
            <div style={styles.browserHeader}>
              <div style={{ display: "flex", gap: "6px" }}>
                <div style={{ width: "10px", height: "10px", borderRadius: "50%", background: "#ef4444" }} />
                <div style={{ width: "10px", height: "10px", borderRadius: "50%", background: "#f59e0b" }} />
                <div style={{ width: "10px", height: "10px", borderRadius: "50%", background: "#10b981" }} />
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: "11px", color: "#71717a" }}>
                <span>◀</span> <span>▶</span> <span>🔄</span>
              </div>

              <div style={styles.urlBar}>
                🔒 https://{platform}.com/{authorHandle}/status/194029481
              </div>

              <div style={{ fontSize: "11px", color: "#71717a" }}>⋮</div>
            </div>

            {/* Widescreen 3-Column Web App Body */}
            <div style={styles.laptopAppBody}>
              {/* Left Column: Navigation Sidebar */}
              <div style={styles.laptopNavColumn}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", padding: "6px 8px", marginBottom: "10px" }}>
                  <span style={{ fontSize: "18px" }}>{platformConfig.icon}</span>
                  <span style={{ fontWeight: "800", fontSize: "14px", color: "#fff" }}>{platformConfig.name}</span>
                </div>

                <div style={styles.laptopNavItemActive}>
                  <span>🏠</span> <span>Home</span>
                </div>
                <div style={styles.laptopNavItem}>
                  <span>🔍</span> <span>Explore</span>
                </div>
                <div style={styles.laptopNavItem}>
                  <span>🔔</span> <span>Notifications</span>
                </div>
                <div style={styles.laptopNavItem}>
                  <span>✉️</span> <span>Messages</span>
                </div>
                <div style={styles.laptopNavItem}>
                  <span>👤</span> <span>Profile</span>
                </div>

                <button style={{ ...styles.laptopPostBtn, background: platformConfig.accent }}>
                  Post
                </button>
              </div>

              {/* Center Column: Main Scrollable Feed */}
              <div style={styles.laptopCenterFeed}>
                {/* Composer Box */}
                <div style={styles.laptopComposerCard}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <div style={{ width: "30px", height: "30px", borderRadius: "50%", background: "linear-gradient(135deg, #6366f1, #a855f7)", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontWeight: "bold", fontSize: "12px" }}>
                      {authorName.charAt(0)}
                    </div>
                    <span style={{ fontSize: "12px", color: "#64748b" }}>What is happening?!</span>
                  </div>
                </div>

                {/* Focal 2.5D Post Card Spanning Full Column Width */}
                <div style={{ width: "100%", marginBottom: "12px" }}>
                  {renderPostCard()}
                </div>

                {/* Reply Stream Preview */}
                <div style={styles.laptopRepliesContainer}>
                  <span style={{ fontSize: "10px", fontWeight: "700", color: "#94a3b8", display: "block", marginBottom: "6px" }}>
                    TOP REPLIES (2)
                  </span>
                  <div style={{ display: "flex", gap: "8px", fontSize: "11px", color: "#cbd5e1" }}>
                    <div style={{ width: "24px", height: "24px", borderRadius: "50%", background: "#ec4899", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontWeight: "bold", fontSize: "10px" }}>S</div>
                    <div>
                      <span style={{ fontWeight: "700", color: "#fff" }}>Sarah Miller</span>
                      <span style={{ color: "#64748b", marginLeft: "4px" }}>@sarah_ui</span>
                      <p style={{ margin: "2px 0 0 0", color: "#94a3b8", fontSize: "11px" }}>Love the 3D spatial depth on this preview! Increible detail. 🚀</p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Right Column: Trending & Search */}
              <div style={styles.laptopRightSidebar}>
                <div style={styles.laptopSearchInput}>
                  <span>🔍</span> <span style={{ color: "#64748b", fontSize: "10px" }}>Search {platformConfig.name}</span>
                </div>

                <div style={styles.laptopWidgetCard}>
                  <span style={{ fontSize: "11px", fontWeight: "800", color: "#fff", display: "block", marginBottom: "8px" }}>
                    Trending for you
                  </span>
                  <div style={{ marginBottom: "8px" }}>
                    <span style={{ fontSize: "9px", color: "#64748b" }}>Technology • Trending</span>
                    <div style={{ fontSize: "10px", fontWeight: "700", color: "#e2e8f0" }}>#2Point5DStudio</div>
                    <span style={{ fontSize: "9px", color: "#64748b" }}>18.4K posts</span>
                  </div>
                  <div>
                    <span style={{ fontSize: "9px", color: "#64748b" }}>Design • Trending</span>
                    <div style={{ fontSize: "10px", fontWeight: "700", color: "#e2e8f0" }}>#ReactSpatialUI</div>
                    <span style={{ fontSize: "9px", color: "#64748b" }}>9.2K posts</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Laptop Base Chassis */}
          <div style={styles.laptopBase}>
            <div style={styles.thumbNotch} />
          </div>
        </div>
      );
    }

    if (device === "desktop") {
      return (
        <div style={styles.desktopWrapper}>
          <div style={styles.desktopMonitor}>
            {/* Desktop Window Title Bar */}
            <div style={styles.desktopHeader}>
              <div style={{ display: "flex", gap: "6px" }}>
                <div style={{ width: "10px", height: "10px", borderRadius: "50%", background: "#ef4444" }} />
                <div style={{ width: "10px", height: "10px", borderRadius: "50%", background: "#f59e0b" }} />
                <div style={{ width: "10px", height: "10px", borderRadius: "50%", background: "#10b981" }} />
              </div>
              <span style={{ fontSize: "11px", fontWeight: "700", color: "#e2e8f0" }}>
                Social Studio Pro — 32" Spatial Studio Display
              </span>
              <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "8px" }}>
                <span style={{ fontSize: "9px", background: "rgba(16, 185, 129, 0.2)", color: "#10b981", border: "1px solid rgba(16,185,129,0.3)", padding: "2px 6px", borderRadius: "4px", fontWeight: "700" }}>● LIVE SYNC</span>
                <span style={{ fontSize: "10px", color: "#a1a1aa" }}>v2.5 Spatial</span>
              </div>
            </div>

            {/* Full 3-Column Desktop Application Workspace */}
            <div style={styles.desktopAppBody}>
              {/* Left Column: App Rail */}
              <div style={styles.desktopNavRail}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", padding: "8px 10px", borderBottom: "1px solid rgba(255,255,255,0.06)", marginBottom: "8px" }}>
                  <div style={{ width: "26px", height: "26px", borderRadius: "6px", background: "linear-gradient(135deg, #6366f1, #a855f7)", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontWeight: "bold", fontSize: "12px" }}>S</div>
                  <div>
                    <div style={{ fontSize: "11px", fontWeight: "700", color: "#fff" }}>Social Studio</div>
                    <div style={{ fontSize: "9px", color: "#64748b" }}>Pro Workspace</div>
                  </div>
                </div>

                <div style={{ padding: "0 4px" }}>
                  <div style={styles.desktopNavItemActive}>
                    <span>🚀</span> <span>Live Preview</span>
                  </div>
                  <div style={styles.desktopNavItem}>
                    <span>📊</span> <span>Analytics</span>
                  </div>
                  <div style={styles.desktopNavItem}>
                    <span>🗓️</span> <span>Schedule</span>
                  </div>
                  <div style={styles.desktopNavItem}>
                    <span>🖼️</span> <span>Assets</span>
                  </div>
                </div>
              </div>

              {/* Center Main Workspace Canvas */}
              <div style={styles.desktopCenterCanvas}>
                {/* Workspace Header Banner */}
                <div style={styles.desktopWorkspaceBanner}>
                  <div>
                    <span style={{ fontSize: "12px", fontWeight: "800", color: "#fff" }}>
                      Active Post Canvas ({platformConfig.name})
                    </span>
                    <span style={{ fontSize: "10px", color: "#94a3b8", display: "block" }}>
                      2.5D Layer Depth Stage • Realtime Viewport Fit
                    </span>
                  </div>
                  <button style={{ ...styles.desktopBannerBtnActive, background: platformConfig.accent }}>
                    Publish Post
                  </button>
                </div>

                {/* Focal 2.5D Post Card Spanning Center Column */}
                <div style={{ width: "100%", maxWidth: "580px", margin: "0 auto", padding: "10px 0" }}>
                  {renderPostCard()}
                </div>

                {/* Live Metrics Row */}
                <div style={styles.desktopMetricsRow}>
                  <div style={styles.desktopMetricCard}>
                    <span style={{ fontSize: "9px", color: "#64748b" }}>EST. IMPRESSIONS</span>
                    <span style={{ fontSize: "13px", fontWeight: "800", color: "#10b981" }}>24.5K ↗</span>
                  </div>
                  <div style={styles.desktopMetricCard}>
                    <span style={{ fontSize: "9px", color: "#64748b" }}>ENGAGEMENT RATE</span>
                    <span style={{ fontSize: "13px", fontWeight: "800", color: "#6366f1" }}>6.2%</span>
                  </div>
                  <div style={styles.desktopMetricCard}>
                    <span style={{ fontSize: "9px", color: "#64748b" }}>VIRAL SCORE</span>
                    <span style={{ fontSize: "13px", fontWeight: "800", color: "#f59e0b" }}>92/100</span>
                  </div>
                </div>
              </div>

              {/* Right Column: Inspector Panel */}
              <div style={styles.desktopInspectorPanel}>
                <span style={{ fontSize: "11px", fontWeight: "800", color: "#fff", display: "block", marginBottom: "8px" }}>
                  Post Inspector
                </span>

                <div style={styles.inspectorWidget}>
                  <span style={{ fontSize: "10px", fontWeight: "700", color: "#e2e8f0" }}>Aspect Ratio</span>
                  <span style={{ fontSize: "9px", color: "#10b981", display: "block", marginTop: "2px" }}>✓ Optimized for {device}</span>
                </div>

                <div style={styles.inspectorWidget}>
                  <span style={{ fontSize: "10px", fontWeight: "700", color: "#e2e8f0" }}>Parallax Elevation</span>
                  <span style={{ fontSize: "9px", color: "#94a3b8", display: "block", marginTop: "2px" }}>Active: {layerElevation}px Z-depth</span>
                </div>

                <div style={styles.inspectorWidget}>
                  <span style={{ fontSize: "10px", fontWeight: "700", color: "#e2e8f0" }}>Optimal Schedule</span>
                  <span style={{ fontSize: "9px", color: "#38bdf8", display: "block", marginTop: "2px" }}>Today at 6:30 PM</span>
                </div>
              </div>
            </div>
          </div>

          {/* Desktop Stand */}
          <div style={styles.desktopStandNeck} />
          <div style={styles.desktopStandBase} />
        </div>
      );
    }
  };

  return (
    <div style={{
      ...styles.appContainer,
      position: isFullscreen ? "fixed" : "relative",
      top: isFullscreen ? 0 : "auto",
      left: isFullscreen ? 0 : "auto",
      zIndex: isFullscreen ? 9999 : 1,
      borderRadius: isFullscreen ? "0" : "16px",
      boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
      width: "100%",
      height: isFullscreen ? "100vh" : "800px",
    }}>
      {/* Inject CSS */}
      <style>{EMBEDDED_CSS}</style>

      {/* Top Header Controls Bar */}
      <header style={styles.topHeader}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <div style={styles.logoBadge}>2.5D</div>
          <div>
            <h1 style={{ fontSize: "15px", fontWeight: "800", color: "#fff", letterSpacing: "-0.02em" }}>
              2.5D Social Studio
            </h1>
            <span style={{ fontSize: "11px", color: "#71717a" }}>
              Multi-Platform & Viewport Spatial Previewer
            </span>
          </div>
        </div>

        {/* Viewport Device Switcher */}
        <div style={styles.segmentedControl}>
          {[
            { id: "mobile", label: "📱 Mobile (iPhone)", icon: "📱" },
            { id: "laptop", label: "💻 Laptop (MacBook)", icon: "💻" },
            { id: "desktop", label: "🖥️ Desktop (32\" Studio)", icon: "🖥️" }
          ].map((d) => (
            <button
              key={d.id}
              onClick={() => setDevice(d.id)}
              className={`tweak-btn ${device === d.id ? "active" : ""}`}
            >
              {d.label}
            </button>
          ))}
        </div>

        {/* Platform Smart Selector */}
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <div style={styles.segmentedControl}>
            {Object.keys(platformConfigs).map((pKey) => {
              const p = platformConfigs[pKey as keyof typeof platformConfigs];
              return (
                <button
                  key={pKey}
                  onClick={() => setPlatform(pKey)}
                  className={`tweak-btn ${platform === pKey ? "active" : ""}`}
                  style={{
                    background: platform === pKey ? p.accent : undefined
                  }}
                >
                  <span>{p.icon}</span> <span>{p.name}</span>
                </button>
              );
            })}
          </div>
          <button
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="tweak-btn"
            style={{ padding: "6px" }}
            title="Toggle Fullscreen"
          >
            {isFullscreen ? "↙️" : "↗️"}
          </button>
        </div>
      </header>

      {/* Main Workspace Split View */}
      <div style={styles.mainWorkspace}>
        {/* Left Control Drawer Sidebar */}
        <aside className="glass-panel" style={styles.controlDrawer}>
          {/* Section 1: Spatial Angle Presets */}
          <div style={styles.drawerSection}>
            <span style={styles.sectionLabel}>SPATIAL VIEW ANGLES</span>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px", marginTop: "8px" }}>
              {[
                { id: "isometric", label: "Isometric 3D" },
                { id: "hero", label: "Hero Perspective" },
                { id: "tiltRight", label: "Tilt Right" },
                { id: "tiltLeft", label: "Tilt Left" },
                { id: "topDown", label: "Top Down" },
                { id: "flat", label: "Flat 2D" }
              ].map((ap) => (
                <button
                  key={ap.id}
                  onClick={() => applyAnglePreset(ap.id)}
                  className={`tweak-btn ${anglePreset === ap.id ? "active" : ""}`}
                  style={{ justifyContent: "center", fontSize: "11px", padding: "6px" }}
                >
                  {ap.label}
                </button>
              ))}
            </div>
          </div>

          {/* Section 2: 3D Motion Animation Presets */}
          <div style={styles.drawerSection}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={styles.sectionLabel}>3D MOTION PRESETS</span>
              <button
                onClick={() => setIsPlaying(!isPlaying)}
                style={{
                  background: isPlaying ? "rgba(16, 185, 129, 0.2)" : "rgba(239, 68, 68, 0.2)",
                  color: isPlaying ? "#10b981" : "#ef4444",
                  border: "none",
                  borderRadius: "4px",
                  padding: "2px 6px",
                  fontSize: "10px",
                  fontWeight: "700",
                  cursor: "pointer"
                }}
              >
                {isPlaying ? "▶ PLAYING" : "⏸ PAUSED"}
              </button>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "6px", marginTop: "8px" }}>
              {[
                { id: "floatingWave", name: "Floating Wave", desc: "Gentle sine float & pitch sway" },
                { id: "turntableOrbit", name: "360° Orbit Showcase", desc: "Continuous turntable rotation" },
                { id: "pulseElevate", name: "Pulse & Elevate", desc: "Breathing Z-depth & active glow" },
                { id: "none", name: "Static (No Motion)", desc: "Manual pitch/yaw mouse control" }
              ].map((anim) => (
                <div
                  key={anim.id}
                  onClick={() => {
                    setAnimationPreset(anim.id);
                    if (anim.id !== "none") setIsPlaying(true);
                  }}
                  className={`preset-card ${animationPreset === anim.id ? "active" : ""}`}
                >
                  <div style={{ fontSize: "12px", fontWeight: "700", color: "#fff" }}>{anim.name}</div>
                  <div style={{ fontSize: "10px", color: "#a1a1aa", marginTop: "2px" }}>{anim.desc}</div>
                </div>
              ))}
            </div>

            {/* Animation Speed Selector */}
            {animationPreset !== "none" && (
              <div style={{ display: "flex", alignItems: "center", gap: "6px", marginTop: "8px" }}>
                <span style={{ fontSize: "10px", color: "#71717a", fontWeight: "600" }}>SPEED:</span>
                {["slow", "normal", "fast"].map((sp) => (
                  <button
                    key={sp}
                    onClick={() => setAnimationSpeed(sp)}
                    className={`tweak-btn ${animationSpeed === sp ? "active" : ""}`}
                    style={{ padding: "2px 8px", fontSize: "10px" }}
                  >
                    {sp.toUpperCase()}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Section 3: Media Format Switcher */}
          <div style={styles.drawerSection}>
            <span style={styles.sectionLabel}>MEDIA ATTACHMENT FORMAT</span>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px", marginTop: "8px" }}>
              {[
                { id: "single", label: "Single Image" },
                { id: "grid", label: "Photo Grid" },
                { id: "video", label: "Video Player" },
                { id: "poll", label: "Poll Voting" }
              ].map((m) => (
                <button
                  key={m.id}
                  onClick={() => setMediaType(m.id)}
                  className={`tweak-btn ${mediaType === m.id ? "active" : ""}`}
                  style={{ justifyContent: "center", fontSize: "11px" }}
                >
                  {m.label}
                </button>
              ))}
            </div>
          </div>

          {/* Section 4: 2.5D Depth Elevation Slider */}
          <div style={styles.drawerSection}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", marginBottom: "6px" }}>
              <span style={styles.sectionLabel}>PARALLAX LAYER ELEVATION</span>
              <span style={{ color: platformConfig.accent, fontWeight: "700" }}>{layerElevation}px</span>
            </div>
            <input
              type="range"
              min="0"
              max="50"
              value={layerElevation}
              onChange={(e) => setLayerElevation(Number(e.target.value))}
              style={{ width: "100%", accentColor: platformConfig.accent }}
            />
          </div>

          {/* Section 5: Live Post Editor */}
          <div style={styles.drawerSection}>
            <span style={styles.sectionLabel}>POST CONTENT EDITOR</span>
            <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginTop: "8px" }}>
              <div>
                <label style={styles.inputLabel}>Author Name</label>
                <input
                  type="text"
                  value={authorName}
                  onChange={(e) => setAuthorName(e.target.value)}
                  style={styles.textInput}
                />
              </div>

              <div>
                <label style={styles.inputLabel}>Caption Text</label>
                <textarea
                  rows={3}
                  value={postCaption}
                  onChange={(e) => setPostCaption(e.target.value)}
                  style={{ ...styles.textInput, resize: "none" }}
                />
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <input
                  type="checkbox"
                  id="verified"
                  checked={isVerified}
                  onChange={(e) => setIsVerified(e.target.checked)}
                  style={{ accentColor: platformConfig.accent }}
                />
                <label htmlFor="verified" style={{ fontSize: "11px", color: "#d4d4d8", cursor: "pointer" }}>
                  Show Verified Badge
                </label>
              </div>
            </div>
          </div>
        </aside>

        {/* Right Preview Canvas Stage */}
        <main
          ref={canvasRef}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerLeave={handlePointerUp}
          style={styles.canvasStage}
        >
          {/* Floor Grid Background */}
          {enableFloorGrid && <div className="floor-grid" />}

          {/* Top Canvas HUD Overlay */}
          <div style={styles.canvasHUD}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <span style={{ fontSize: "11px", fontWeight: "700", color: "#fff" }}>
                SPATIAL TELEMETRY
              </span>
              <span style={styles.hudBadge}>PITCH: {pitch}°</span>
              <span style={styles.hudBadge}>YAW: {yaw}°</span>
              <span style={styles.hudBadge}>ROLL: {roll}°</span>
              <span style={styles.hudBadge}>ZOOM: {Math.round(zoom * 100)}%</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ fontSize: "10px", color: "#a1a1aa" }}>🖱️ Drag canvas to orbit • Scroll to zoom</span>
              <button
                onClick={() => setEnableFloorGrid(!enableFloorGrid)}
                className={`tweak-btn ${enableFloorGrid ? "active" : ""}`}
                style={{ padding: "2px 6px", fontSize: "10px" }}
              >
                Grid
              </button>
            </div>
          </div>

          {/* Centered 3D Perspective Stage */}
          <div className="perspective-stage" style={styles.perspectiveStageContainer}>
            {/* Decoupled Interactive Pitch/Yaw Orbit Wrapper */}
            <div
              style={{
                transform: `scale(${zoom}) rotateX(${pitch}deg) rotateY(${yaw}deg) rotateZ(${roll}deg)`,
                transformStyle: "preserve-3d",
                transition: isDragging.current ? "none" : "transform 0.15s cubic-bezier(0.2, 0, 0, 1)",
                display: "flex",
                justifyContent: "center",
                alignItems: "center"
              }}
            >
              {/* Motion Keyframe Animation Wrapper */}
              <div
                className={
                  isPlaying && animationPreset !== "none"
                    ? `anim-${animationPreset}`
                    : ""
                }
                style={{
                  transformStyle: "preserve-3d",
                  animationDuration:
                    animationSpeed === "slow"
                      ? "10s"
                      : animationSpeed === "fast"
                      ? "3s"
                      : "6s"
                }}
              >
                {renderDevice()}
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

