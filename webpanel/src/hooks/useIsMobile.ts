import { Grid } from "antd";

const { useBreakpoint } = Grid;

/**
 * True on phone-sized screens (< md / 768px). Uses the same AntD breakpoint the
 * shell (Layout) uses to switch the sidebar into a drawer, so list pages can
 * swap a wide table for a stacked card view on mobile.
 */
export function useIsMobile(): boolean {
  const screens = useBreakpoint();
  // `md` is undefined on first paint; treat that as desktop to avoid a flash.
  return screens.md === false;
}
