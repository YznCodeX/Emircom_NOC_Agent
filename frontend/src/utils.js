import { SLA_MINUTES, TEAM_NAMES, TEAM_EMAILS } from './constants'

export function generateEmailTemplate(ticket, a) {
  const severity = a.Severity || ticket.Severity || 'Medium'
  const category = ticket.Category || 'Unknown'
  const team = TEAM_NAMES[category] || 'NOC Team'
  const teamEmail = TEAM_EMAILS[category] || 'noc@emircom.com'
  const slaLabel = SLA_MINUTES[severity] < 60
    ? `${SLA_MINUTES[severity]} minutes`
    : `${SLA_MINUTES[severity] / 60} hour(s)`

  return `To: ${teamEmail}
Subject: [NOC Alert] ${severity} Severity — ${category} Incident — ${a.Affected_Node || 'Unknown Node'}

Dear ${team},

An automated NOC AI analysis has identified the following ${severity.toLowerCase()} severity incident requiring your attention.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INCIDENT DETAILS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Ticket ID:      ${ticket.Ticket_ID}
Severity:       ${severity}
Category:       ${category}
Affected Node:  ${a.Affected_Node || 'Unknown'}
Categorization: ${a.Categorization || 'Unknown'}

SYMPTOM
━━━━━━━━
${a.Symptom_Description || 'N/A'}

ROOT CAUSE
━━━━━━━━━━
${a.Root_Cause || 'N/A'}

BUSINESS IMPACT
━━━━━━━━━━━━━━━
${a.Business_Impact || 'N/A'}

RECOMMENDED ACTION
━━━━━━━━━━━━━━━━━━
${a.Recommended_Action || 'N/A'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SLA Window: ${slaLabel} from ticket creation.
AI Confidence Score: ${a.Confidence_Score || 'N/A'}%${a.Confidence_Reason ? `\nReason: ${a.Confidence_Reason}` : ''}

Please acknowledge this ticket in GLPI and begin remediation immediately.

Regards,
Emircom NOC AI Agent
Generated: ${new Date().toLocaleString()}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`
}
