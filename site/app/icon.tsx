import { ImageResponse } from "next/og";

export const size = {
  width: 64,
  height: 64,
};

export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    <div
      style={{
        alignItems: "center",
        background: "#0b0d11",
        border: "2px solid #272c34",
        borderRadius: "12px",
        color: "#f2f4f7",
        display: "flex",
        fontFamily: "monospace",
        fontSize: 32,
        fontWeight: 700,
        height: "100%",
        justifyContent: "center",
        width: "100%",
      }}
    >
      <span>r</span>
      <span style={{ color: "#73b7ff" }}>_</span>
    </div>,
    size,
  );
}
