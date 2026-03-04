"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useLocale } from "@/i18n";

interface TourStep {
  target: string; // data-tour attribute value
  title: string;
  description: string;
  position: "top" | "bottom" | "left" | "right";
  beforeShow?: () => void;
}

interface OnboardingTourProps {
  onComplete: () => void;
  onOpenSidebar: () => void;
  onCloseSidebar: () => void;
}

export function OnboardingTour({
  onComplete,
  onOpenSidebar,
  onCloseSidebar,
}: OnboardingTourProps) {
  const { t } = useLocale();
  const [currentStep, setCurrentStep] = useState(0);
  const [targetRect, setTargetRect] = useState<DOMRect | null>(null);
  const observerRef = useRef<ResizeObserver | null>(null);
  const isMobile = typeof window !== "undefined" && window.innerWidth < 768;

  const steps: TourStep[] = [
    {
      target: "chat-input",
      title: t.tourStep1Title,
      description: t.tourStep1Desc,
      position: "top",
      beforeShow: () => {
        if (isMobile) onCloseSidebar();
      },
    },
    {
      target: "conversation-list",
      title: t.tourStep2Title,
      description: t.tourStep2Desc,
      position: "right",
      beforeShow: () => {
        if (isMobile) onOpenSidebar();
      },
    },
    {
      target: "telegram-setup",
      title: t.tourStep3Title,
      description: t.tourStep3Desc,
      position: "right",
      beforeShow: () => {
        if (isMobile) onOpenSidebar();
      },
    },
    {
      target: "", // centered card, no target
      title: t.tourStep4Title,
      description: t.tourStep4Desc,
      position: "bottom",
      beforeShow: () => {
        if (isMobile) onCloseSidebar();
      },
    },
  ];

  const totalSteps = steps.length;
  const step = steps[currentStep];
  const isLastStep = currentStep === totalSteps - 1;
  const isCentered = !step.target;

  // Find the visible element with matching data-tour (handles desktop/mobile dual Sidebar)
  const findVisibleTarget = useCallback((target: string): Element | null => {
    const els = document.querySelectorAll(`[data-tour="${target}"]`);
    for (const el of els) {
      const rect = el.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) return el;
    }
    return null;
  }, []);

  const updateRect = useCallback(() => {
    if (!step.target) {
      setTargetRect(null);
      return;
    }
    const el = findVisibleTarget(step.target);
    if (el) {
      setTargetRect(el.getBoundingClientRect());
    }
  }, [step.target, findVisibleTarget]);

  useEffect(() => {
    step.beforeShow?.();

    // Small delay to let sidebar open/DOM settle before measuring
    const timer = setTimeout(() => {
      updateRect();
    }, 150);

    return () => {
      clearTimeout(timer);
    };
  }, [currentStep, updateRect, step]);

  // ResizeObserver + window resize to reposition
  useEffect(() => {
    if (!step.target) return;

    const el = findVisibleTarget(step.target);
    if (!el) return;

    observerRef.current = new ResizeObserver(() => updateRect());
    observerRef.current.observe(el);

    const handleResize = () => updateRect();
    window.addEventListener("resize", handleResize);

    return () => {
      observerRef.current?.disconnect();
      window.removeEventListener("resize", handleResize);
    };
  }, [step.target, updateRect]);

  const goNext = () => {
    if (isLastStep) {
      onComplete();
      return;
    }
    setCurrentStep((s) => s + 1);
  };

  const goPrev = () => {
    if (currentStep === 0) return;
    setCurrentStep((s) => s - 1);
  };

  const skip = () => {
    if (isMobile) onCloseSidebar();
    onComplete();
  };

  // Compute tooltip position
  const getTooltipStyle = (): React.CSSProperties => {
    // Mobile: always center the tooltip for reliability
    if (isMobile || isCentered || !targetRect) {
      return {
        position: "fixed",
        top: "50%",
        left: "50%",
        transform: "translate(-50%, -50%)",
      };
    }

    // Desktop: position relative to target
    const gap = 12;
    const margin = 16;
    const tooltipHeight = 220; // approximate max tooltip height
    const style: React.CSSProperties = { position: "fixed" };

    switch (step.position) {
      case "top":
        style.bottom = window.innerHeight - targetRect.top + gap;
        style.left = targetRect.left + targetRect.width / 2;
        style.transform = "translateX(-50%)";
        break;
      case "bottom":
        style.top = targetRect.bottom + gap;
        style.left = targetRect.left + targetRect.width / 2;
        style.transform = "translateX(-50%)";
        break;
      case "left":
        style.top = Math.min(
          targetRect.top + targetRect.height / 2 - tooltipHeight / 2,
          window.innerHeight - tooltipHeight - margin,
        );
        style.right = window.innerWidth - targetRect.left + gap;
        break;
      case "right":
        style.top = Math.min(
          targetRect.top + targetRect.height / 2 - tooltipHeight / 2,
          window.innerHeight - tooltipHeight - margin,
        );
        style.left = targetRect.right + gap;
        break;
    }

    return style;
  };

  // Highlight cutout style
  const getCutoutStyle = (): React.CSSProperties | null => {
    if (isCentered || !targetRect) return null;
    const pad = 6;
    return {
      position: "fixed",
      top: targetRect.top - pad,
      left: targetRect.left - pad,
      width: targetRect.width + pad * 2,
      height: targetRect.height + pad * 2,
      borderRadius: 8,
      boxShadow: "0 0 0 9999px rgba(0, 0, 0, 0.6)",
      zIndex: 60,
      pointerEvents: "none",
    };
  };

  const cutout = getCutoutStyle();

  return (
    <>
      {/* Backdrop — only for centered step (step 4) since cutout handles overlay for others */}
      {isCentered && (
        <div className="fixed inset-0 bg-black/60 z-[60]" />
      )}

      {/* Cutout highlight */}
      {cutout && <div style={cutout} />}

      {/* Tooltip */}
      <div
        style={getTooltipStyle()}
        className="z-[70] w-[320px] max-w-[calc(100vw-32px)] bg-white dark:bg-gray-800 rounded-xl shadow-2xl p-5"
      >
        {/* Step indicator */}
        <div className="text-xs text-gray-400 dark:text-gray-500 mb-2">
          {t.tourStep} {currentStep + 1} {t.tourOf} {totalSteps}
        </div>

        {/* Title */}
        <h3 className="text-base font-semibold text-gray-900 dark:text-white mb-1.5">
          {step.title}
        </h3>

        {/* Description */}
        <p className="text-sm text-gray-600 dark:text-gray-300 leading-relaxed mb-4">
          {step.description}
        </p>

        {/* Navigation */}
        <div className="flex items-center justify-between">
          <button
            onClick={skip}
            className="text-sm text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
          >
            {t.tourSkip}
          </button>

          <div className="flex items-center gap-2">
            {currentStep > 0 && (
              <button
                onClick={goPrev}
                className="text-sm px-3 py-1.5 rounded-lg text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              >
                {t.tourPrev}
              </button>
            )}
            <button
              onClick={goNext}
              className="text-sm px-4 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors font-medium"
            >
              {isLastStep ? t.tourDone : t.tourNext}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
