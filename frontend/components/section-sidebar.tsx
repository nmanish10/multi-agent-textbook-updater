type SectionSidebarProps = {
  sections: Array<{
    section_id: string;
    title: string;
    has_updates?: boolean;
  }>;
};

export function SectionSidebar({ sections }: SectionSidebarProps) {
  return (
    <div className="sidebarBlock">
      <p className="sidebarTitle">Inside this chapter</p>
      {sections.length === 0 ? (
        <p className="sidebarNote">No section structure was recovered for this chapter yet.</p>
      ) : (
        <div className="sidebarNavList">
          {sections.map((section) => (
            <a key={section.section_id} href={`#${section.section_id}`} className="sidebarLink stacked">
              <span>{section.section_id}</span>
              <strong>{section.title}</strong>
              {section.has_updates ? <span className="sidebarMiniBadge">Updated</span> : null}
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
