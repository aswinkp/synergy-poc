import { Check, Circle, LoaderCircle, Sparkles } from 'lucide-react'
import type { AgentStep } from './types'

interface AgentActivityProps {
  steps: AgentStep[]
  complete: boolean
}

export default function AgentActivity({ steps, complete }: AgentActivityProps) {
  return (
    <section className={`agent-activity ${complete ? 'complete' : ''}`} aria-live="polite" aria-label="Agent activity">
      <div className="agent-activity-heading">
        <span className="agent-activity-icon"><Sparkles size={16} /></span>
        <div>
          <strong>{complete ? 'Objective completed' : 'Working on your objective'}</strong>
          <span>{complete ? 'The analysis is ready.' : 'The agent is working through this request.'}</span>
        </div>
      </div>
      <ol>
        {steps.map((step) => (
          <li key={step.id} className={step.status}>
            <span className="agent-step-status" aria-label={step.status}>
              {step.status === 'complete' ? <Check size={14} /> : step.status === 'running' ? <LoaderCircle size={14} /> : <Circle size={11} />}
            </span>
            <span className="agent-step-label">{step.result || step.label}</span>
          </li>
        ))}
      </ol>
    </section>
  )
}
