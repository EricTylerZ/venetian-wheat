import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Venetian Wheat",
  description: "Multi-client project dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          fontFamily: "'Segoe UI', system-ui, -apple-system, sans-serif",
          background: "#faf6ee",
          color: "#2c1810",
          lineHeight: 1.5,
        }}
      >
        <div style={{ maxWidth: 900, margin: "0 auto", padding: "1rem" }}>
          {children}
        </div>
      </body>
    </html>
  );
}
