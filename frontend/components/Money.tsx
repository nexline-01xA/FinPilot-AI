import type {Money as MoneyType} from '@/types/api';
export default function Money({value}:{value:MoneyType}){return <span className="tabular-nums">{value.display}</span>}
