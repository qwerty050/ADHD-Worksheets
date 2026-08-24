import React, { useMemo } from 'react';

const excuses = [
  "is on a coffee break.",
  "is MIA.",
  "returned a 404.",
  "is out sick.",
  "got lost in the sauce.",
  "is touching grass.",
  "went to get boba and never came back.",
  "is in a meeting that could have been an email.",
  "rage-quit and became a shepherd.",
  "is debugging their own life choices."
];

export const ExcuseBanner: React.FC<{ role: string }> = ({ role }) => {
  const excuse = useMemo(() => {
    const randomIndex = Math.floor(Math.random() * excuses.length);
    return excuses[randomIndex];
  }, []);

  return (
    <p style={{ fontStyle: 'italic', marginBottom: '1rem', opacity: 0.8 }}>
      {role} {excuse}
    </p>
  );
};
